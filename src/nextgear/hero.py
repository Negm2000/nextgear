"""Draw one held-out session as an animated SVG figure, one frame per event.

Matplotlib draws the static parts once and the changing parts once per frame. The frames are
merged into one SVG that shares its font glyphs, and CSS shows one frame at a time.
"""

import io
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .events import INDEX, VOCAB  # noqa: E402
from .rules import PLATFORM  # noqa: E402
from .simulator import State, apply  # noqa: E402

# Computer Modern ships with matplotlib, so the figure looks like LaTeX without a TeX install.
PAPER = {
    "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.unicode_minus": False,
    "axes.formatter.use_mathtext": True, "font.size": 9, "axes.titlesize": 9, "axes.linewidth": 0.6,
    "axes.edgecolor": "black", "xtick.direction": "in", "ytick.direction": "in", "xtick.major.width": 0.6,
    "xtick.major.size": 3, "ytick.major.size": 0, "xtick.labelsize": 8, "ytick.labelsize": 9,
    "svg.fonttype": "path", "svg.hashsalt": "nextgear", "figure.facecolor": "white", "savefig.facecolor": "white",
}
INK, GRU, GREY, LIGHT = "#000000", "#2b5797", "#8c8c8c", "#c8c8c8"

SVG, XLINK = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)
TT = {"family": "monospace", "fontname": "cmtt10"}
NAMES = {"API_GATEWAY": "API Gateway", "AUTH_RESOLVER": "Auth Resolver", "POLICY_MANAGER": "Policy Manager",
         "LICENSE_RESOLVER": "License Resolver", "CHAT_ENGINE": "Chat Engine", "BILLING_LEDGER": "Billing Ledger",
         "SERVERLESS_RUNTIME": "Serverless Runtime", "TENANT_RESOLVER": "Tenant Resolver",
         "USAGE_COLLECTOR": "Usage Collector", "OUTBOUND_API_GATEWAY": "Outbound Gateway", "GRPC_HUB": "gRPC Hub",
         "TYPES_REGISTRY": "Types Registry", "AUTHZ_RESOLVER": "Authz Resolver", "CREDENTIALS_STORE": "Credentials Store",
         "ACCOUNT_MANAGER": "Account Manager", "RESOURCE_GROUP": "Resource Group"}
FACT_LABELS = {"needs the Chat Engine": "Chat Engine", "needs the Billing Ledger": "Billing Ledger",
               "needs the Serverless Runtime": "Serverless Runtime", "needs the Policy Manager": "Policy Manager",
               "needs the License Resolver": "License Resolver", "needs the Usage Collector": "Usage Collector",
               "has a tight latency budget": "tight budget", "agent is careful": "careful agent",
               "agent knows the dependencies": "knows dependencies"}
QUICK = {"STEP_ACCEPTED", "STEP_REVERTED", "ROLLBACK_ASSEMBLY", "ENABLE_RESOLVER_CACHE"}
LOG_LINES, BARS = 9, 5


def _proposed(state: State) -> str | None:
    if state.pending == "local":
        return f"{NAMES[state.gear]}?"
    if state.pending == "revert":
        return f"{NAMES[state.gear]} (rejected)"
    return None


def _path_text(state: State) -> str:
    parts = [NAMES[g] for g in state.path] + (["Outbound Gateway"] if state.outbound else [])
    if _proposed(state) and state.gear not in PLATFORM:
        parts.append(_proposed(state))
    text = r" $\rightarrow$ ".join(parts) if parts else "empty"
    if state.pending == "system":
        text += r"  $\vdash$ submitted"
    return text + ("   [resolver cache on]" if state.cache else "")


def _platform_text(state: State) -> str:
    parts = [NAMES[g] for g in PLATFORM if g in state.platform]
    if _proposed(state) and state.gear in PLATFORM:
        parts.append(_proposed(state))
    return ", ".join(parts) if parts else "none"


class _Figure:
    """The axes and every static artist; `dynamic` holds what one frame adds."""

    def __init__(self, truth: dict[str, bool]):
        self.fig = f = plt.figure(figsize=(9.6, 3.7))
        self.static = [f.text(0.01, 0.93, r"request path $s_t$:", fontsize=10),
                       f.text(0.01, 0.875, "platform gears:", fontsize=10)]
        self.log = f.add_axes((0.01, 0.06, 0.23, 0.7))
        self.bars = f.add_axes((0.435, 0.14, 0.185, 0.62))
        self.belief = f.add_axes((0.795, 0.14, 0.125, 0.62))
        self.log.axis("off")
        self.log.set_xlim(0, 1)
        self.log.set_ylim(LOG_LINES - 0.5, -0.9)
        self.static.append(self.log.set_title(r"(a) events $e_1, \ldots, e_t$", loc="left", fontsize=10))
        for ax, rows in ((self.bars, BARS), (self.belief, len(truth))):
            ax.set_xlim(0, 1)
            ax.set_ylim(rows - 0.5, -0.6)
            ax.set_yticks([])
            ax.set_xticks([0, 0.5, 1])
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
        self.static.append(self.bars.set_title(r"(b) forecast of $e_t$ from $e_{1:t-1}$", loc="left", fontsize=10,
                                               x=-0.75))
        self.static.append(self.bars.set_xlabel("probability", fontsize=9))
        handles = [plt.Rectangle((0, 0), 1, 1, color=GRU), plt.Rectangle((0, 0), 1, 1, fill=False, ec=INK, lw=0.8)]
        self.static.append(self.bars.legend(handles, [r"GRU $p_\theta$", r"oracle $p^\ast$"], loc="upper right",
                                            bbox_to_anchor=(-0.08, -0.04), frameon=False, fontsize=8,
                                            handlelength=1.2, ncol=2))
        self.static.append(self.belief.set_title(r"(c) oracle's belief $p(z \mid e_{1:t})$", loc="left",
                                                 fontsize=10, x=-0.78))
        self.static.append(self.belief.set_xlabel("probability", fontsize=9))
        self.static.append(self.belief.text(1.32, -0.95, "true", ha="center", va="center", fontsize=8.5,
                                            style="italic"))
        for y, (fact, value) in enumerate(truth.items()):
            self.static.append(self.belief.text(-0.06, y, FACT_LABELS[fact], ha="right", va="center", fontsize=8.5))
            self.static.append(self.belief.text(1.32, y, "yes" if value else "no", ha="center", va="center",
                                                fontsize=8.5, color=INK if value else GREY))
        self.dynamic = []

    def svg(self) -> str:
        buffer = io.StringIO()
        self.fig.savefig(buffer, format="svg")
        return buffer.getvalue()

    def hide_static(self) -> None:
        self.fig.patch.set_visible(False)
        for ax in (self.log, self.bars, self.belief):
            ax.patch.set_visible(False)
            ax.axis("off")
        for artist in self.static:
            artist.set_visible(False)

    def add(self, artist):
        artist.set_clip_on(False)
        self.dynamic.append(artist)

    def clear(self) -> None:
        for artist in self.dynamic:
            artist.remove()
        self.dynamic = []


def _frame(fig: _Figure, events, t: int, state: State, gru: np.ndarray, oracle: np.ndarray, belief: dict) -> None:
    """Event t (1-based): the forecast made before it, then what it revealed."""
    event = events[t]
    fig.add(fig.fig.text(0.13, 0.93, _path_text(state), fontsize=10))
    fig.add(fig.fig.text(0.13, 0.875, _platform_text(state), fontsize=10))
    fig.add(fig.fig.text(0.99, 0.93, f"$t = {t}$ of {len(events) - 1}", fontsize=10, ha="right"))
    first = max(1, t - LOG_LINES + 1)
    for line, k in enumerate(range(first, t + 1)):
        if k == t:
            fig.add(fig.log.axhspan(line - 0.45, line + 0.45, color="#ececec", lw=0))
        color = INK if k == t else GREY
        fig.add(fig.log.text(0.02, line, f"{k:>2}", fontsize=9, va="center", color=color, **TT))
        fig.add(fig.log.text(0.15, line, events[k], fontsize=9, va="center", color=color, **TT))
    p, q = gru[t - 1], oracle[t - 1]
    shown = list(np.argsort(-p)[:BARS])
    if INDEX[event] not in shown:
        shown[-1] = INDEX[event]
    for y, k in enumerate(shown):
        actual = VOCAB[k] == event
        fig.add(fig.bars.barh(y, p[k], height=0.56, color=GRU, lw=0)[0])
        fig.add(fig.bars.barh(y, q[k], height=0.74, fill=False, edgecolor=INK, lw=0.8)[0])
        fig.add(fig.bars.text(-0.06, y, VOCAB[k], ha="right", va="center", fontsize=8.5,
                              color=INK if actual else GREY, **TT))
        mark = r"  $\leftarrow e_t$" if actual else ""
        fig.add(fig.bars.text(max(p[k], q[k]) + 0.02, y, f"{p[k]:.2f}{mark}", va="center", fontsize=8.5,
                              color=INK if actual else GREY))
    for y, value in enumerate(belief.values()):
        fig.add(fig.belief.barh(y, value, height=0.56, color=LIGHT, edgecolor=INK, lw=0.5)[0])


def _merge(static: str, frames: list[str], durations: list[float]) -> str:
    """One SVG: shared glyph definitions, the static layer, then one group per frame."""
    defs, layers = {}, []
    for text in [static, *frames]:
        root = ET.fromstring(text)
        for parent in list(root.iter()):
            for child in list(parent):
                if child.tag == f"{{{SVG}}}defs":
                    for item in child:
                        if item.get("id"):
                            defs.setdefault(item.get("id"), item)
                    parent.remove(child)
        for element in root.iter():
            if element.tag != f"{{{SVG}}}svg":
                element.attrib.pop("id", None)
        layers.append(root.find(f"{{{SVG}}}g"))
    total = sum(durations)
    starts = np.cumsum([0, *durations[:-1]])
    css = ["* { stroke-linejoin: round; stroke-linecap: butt }", "svg { --T: %.2fs }" % total, ".frame { opacity: 0 }",
           "@media (prefers-reduced-motion: reduce) { .frame { animation: none !important } .final { opacity: 1 } }"]
    for i, (start, length) in enumerate(zip(starts, durations)):
        a, b = 100 * start / total, 100 * (start + length) / total
        end = f"{b:.3f}% {{ opacity: 0 }}" if i < len(frames) - 1 else "100% { opacity: 1 }"
        css.append(f"@keyframes f{i} {{ 0% {{ opacity: 0 }} {a:.3f}% {{ opacity: 1 }} {end} }}")
        css.append(f".f{i} {{ animation: f{i} var(--T) step-end infinite }}")
    root = ET.fromstring(static)
    for child in list(root):
        root.remove(child)
    root.set("width", "100%")
    root.attrib.pop("height", None)
    ET.SubElement(root, f"{{{SVG}}}title").text = "A held-out session replayed one event at a time"
    definitions = ET.SubElement(root, f"{{{SVG}}}defs")
    ET.SubElement(definitions, f"{{{SVG}}}style").text = "\n".join(css)
    definitions.extend(defs.values())
    root.append(layers[0])
    for i, layer in enumerate(layers[1:]):
        layer.set("class", f"frame f{i}" + (" final" if i == len(frames) - 1 else ""))
        root.append(layer)
    return ET.tostring(root, encoding="unicode")


def render_hero(events, gru_rows: np.ndarray, oracle_rows: np.ndarray, beliefs: list[dict], truth: dict) -> str:
    """`*_rows[t]` is a distribution over events[t + 1]; `beliefs[t]` the oracle's belief after events[t + 1]."""
    n = len(events) - 1
    with plt.rc_context({**PAPER, "font.size": 10}):
        fig = _Figure(truth)
        static = fig.svg()
        fig.hide_static()
        frames, state = [], apply(State(), events[0])
        for t in range(1, n + 1):
            state = apply(state, events[t])
            _frame(fig, events, t, state, gru_rows, oracle_rows, beliefs[t - 1])
            frames.append(fig.svg())
            fig.clear()
        plt.close(fig.fig)
    durations = [0.7 if events[t] in QUICK else 1.3 for t in range(1, n + 1)]
    durations[-1] = 4.5
    return _merge(static, frames, durations)
