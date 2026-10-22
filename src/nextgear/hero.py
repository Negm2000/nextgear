"""Draw one held-out session as an animated SVG figure, one frame per event.

Each frame shows the assembly so far as gear tiles, a plain-language caption of the event, the GRU's and the
oracle's forecast of it, and the oracle's belief about the hidden specification. Matplotlib draws the static
parts once and the changing parts once per frame; the frames are merged into one SVG that shares its font
glyphs, and CSS shows one frame at a time.
"""

import io
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from .events import EVENTS, INDEX, VOCAB  # noqa: E402
from .rules import ORDER, OUTBOUND, PLATFORM, closure, present  # noqa: E402
from .simulator import State, apply  # noqa: E402

# Computer Modern ships with matplotlib, so the figure looks like LaTeX without a TeX install.
PAPER = {
    "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.unicode_minus": False,
    "axes.formatter.use_mathtext": True, "font.size": 9, "axes.titlesize": 9, "axes.linewidth": 0.6,
    "axes.edgecolor": "black", "xtick.direction": "in", "ytick.direction": "in", "xtick.major.width": 0.6,
    "xtick.major.size": 3, "ytick.major.size": 0, "xtick.labelsize": 8, "ytick.labelsize": 9,
    "svg.fonttype": "path", "svg.hashsalt": "nextgear", "figure.facecolor": "white", "savefig.facecolor": "white",
}
INK, GRU, GREY, LIGHT, FAINT, ALERT, DONE = "#000000", "#2b5797", "#8c8c8c", "#c8c8c8", "#e4e4e4", "#b03a2e", "#dbe6f4"

SVG, XLINK = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)
TT = {"family": "monospace", "fontname": "cmtt10"}
# Two-line tile labels.
NAMES = {"API_GATEWAY": "API\nGateway", "AUTH_RESOLVER": "Auth\nResolver", "POLICY_MANAGER": "Policy\nManager",
         "LICENSE_RESOLVER": "License\nResolver", "CHAT_ENGINE": "Chat\nEngine", "BILLING_LEDGER": "Billing\nLedger",
         "SERVERLESS_RUNTIME": "Serverless\nRuntime", "TENANT_RESOLVER": "Tenant\nResolver",
         "USAGE_COLLECTOR": "Usage\nCollector", OUTBOUND: "Outbound\nGateway", "GRPC_HUB": "gRPC\nHub",
         "TYPES_REGISTRY": "Types\nRegistry", "AUTHZ_RESOLVER": "Authz\nResolver",
         "CREDENTIALS_STORE": "Credentials\nStore", "ACCOUNT_MANAGER": "Account\nManager",
         "RESOURCE_GROUP": "Resource\nGroup"}
FACT_LABELS = {"needs the Chat Engine": "Chat Engine", "needs the Billing Ledger": "Billing Ledger",
               "needs the Serverless Runtime": "Serverless Runtime", "needs the Policy Manager": "Policy Manager",
               "needs the License Resolver": "License Resolver", "needs the Usage Collector": "Usage Collector",
               "has a tight latency budget": "tight budget", "agent is careful": "careful agent",
               "agent knows the dependencies": "knows dependencies"}
# Seconds on screen: routine steps pass quickly, verdicts that carry the story linger.
QUICK = {"STEP_ACCEPTED", "STEP_REVERTED", "ENABLE_RESOLVER_CACHE"}
SLOW = {"SUBMIT_ASSEMBLY", "MISSING_DEPENDENCY", "MISSING_CAPABILITY", "EXTERNAL_CALL_VIOLATION", "COST_VIOLATION",
        "LATENCY_VIOLATION", "ORDER_VIOLATION", "BYPASS_VIOLATION", "ROLLBACK_ASSEMBLY"}
BARS = 4
TILE_W, TILE_H, X0, STEP = 0.098, 0.105, 0.135, 0.108
PATH_Y, PLATFORM_Y = 0.888, 0.735


def _slot(gear: str) -> tuple[float, float]:
    """Where a gear's tile sits: request-path gears in documented order, then the outbound gateway, then the
    platform gears on a second row."""
    if gear in PLATFORM:
        return X0 + PLATFORM.index(gear) * STEP, PLATFORM_Y
    return X0 + (7 if gear == OUTBOUND else ORDER[gear]) * STEP, PATH_Y


class _Figure:
    """The axes and every static artist; `dynamic` holds what one frame adds."""

    def __init__(self, truth: dict[str, bool]):
        self.fig = f = plt.figure(figsize=(7.6, 4.35))
        self.static = [f.text(0.01, PATH_Y, "request\npath", fontsize=10, va="center", linespacing=1.1),
                       f.text(0.01, PLATFORM_Y, "platform\ngears", fontsize=10, va="center", linespacing=1.1)]
        # Empty slots, so the shape of a complete assembly is visible from the start.
        for k in range(8):
            self.static.append(self._tile(X0 + k * STEP, PATH_Y, "", FAINT, dashed=True))
        for k in range(len(PLATFORM)):
            self.static.append(self._tile(X0 + k * STEP, PLATFORM_Y, "", FAINT, dashed=True))
        self.static.append(f.add_artist(plt.Line2D([0.01, 0.99], [0.51, 0.51], color=LIGHT, lw=0.6)))
        self.bars = f.add_axes((0.255, 0.065, 0.2, 0.31))
        self.belief = f.add_axes((0.735, 0.065, 0.15, 0.31))
        for ax, rows in ((self.bars, BARS), (self.belief, len(truth))):
            ax.set_xlim(0, 1)
            ax.set_ylim(rows - 0.5, -0.6)
            ax.set_yticks([])
            ax.set_xticks([0, 0.5, 1])
            ax.tick_params(labelsize=8)
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
        self.static.append(f.text(0.01, 0.44, "Forecast of this event, made before it", fontsize=10))
        handles = [plt.Rectangle((0, 0), 1, 1, color=GRU), plt.Rectangle((0, 0), 1, 1, fill=False, ec=INK, lw=0.8)]
        self.static.append(f.legend(handles, ["GRU", "Bayes oracle"], loc="upper left", bbox_to_anchor=(0.005, 0.425),
                                    frameon=False, fontsize=8.5, handlelength=1.2, ncol=2, columnspacing=1.2))
        self.static.append(f.text(0.535, 0.44, "Oracle's belief about the hidden specification", fontsize=10))
        self.static.append(self.belief.text(1.25, -0.95, "true", ha="center", va="center", fontsize=8.5,
                                            style="italic"))
        for y, (fact, value) in enumerate(truth.items()):
            self.static.append(self.belief.text(-0.05, y, FACT_LABELS[fact], ha="right", va="center", fontsize=8.5))
            self.static.append(self.belief.text(1.25, y, "yes" if value else "no", ha="center", va="center",
                                                fontsize=8.5, color=INK if value else GREY))
        self.dynamic = []

    def _tile(self, x, y, label, edge, fill="white", dashed=False, text=INK, lw=0.8):
        box = FancyBboxPatch((x, y - TILE_H / 2), TILE_W, TILE_H, boxstyle="round,pad=0,rounding_size=0.008",
                             transform=self.fig.transFigure, facecolor=fill, edgecolor=edge, lw=lw,
                             linestyle=(0, (3, 2)) if dashed else "-")
        self.fig.add_artist(box)
        if label:
            self.dynamic.append(self.fig.text(x + TILE_W / 2, y, label, ha="center", va="center", fontsize=8.5,
                                              color=text, linespacing=1.05))
        return box

    def svg(self) -> str:
        buffer = io.StringIO()
        self.fig.savefig(buffer, format="svg")
        return buffer.getvalue()

    def hide_static(self) -> None:
        self.fig.patch.set_visible(False)
        for ax in (self.bars, self.belief):
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


def _tiles(fig: _Figure, state: State, event: str) -> None:
    """The assembly after `event`: accepted gears solid, a proposed gear dashed in blue, a rejected one in red,
    and, after a failed dependency check, the missing dependencies outlined in red."""
    built = present(state.path, state.outbound, state.platform)
    done = state.pending == "done" and event == "ASSEMBLY_ADMISSIBLE"
    for gear in sorted(built):
        fig.add(fig._tile(*_slot(gear), NAMES[gear], INK, fill=DONE if done else "white"))
    if state.pending in ("local", "revert") and state.gear not in built:
        rejected = state.pending == "revert"
        fig.add(fig._tile(*_slot(state.gear), NAMES[state.gear], ALERT if rejected else GRU, dashed=True,
                          text=ALERT if rejected else GRU, lw=1.4))
    if event == "MISSING_DEPENDENCY":
        for gear in sorted(closure(built) - built):
            fig.add(fig._tile(*_slot(gear), NAMES[gear], ALERT, dashed=True, text=ALERT, lw=1.4))


def _frame(fig: _Figure, events, t: int, state: State, gru: np.ndarray, oracle: np.ndarray, belief: dict) -> None:
    """Event t (1-based): what it revealed, and the forecasts made before it."""
    event = events[t]
    _tiles(fig, state, event)
    p, q = gru[t - 1], oracle[t - 1]
    fig.add(fig.fig.text(0.01, 0.615, f"{t}/{len(events) - 1}", fontsize=11, color=GREY, va="center"))
    fig.add(fig.fig.text(0.085, 0.615, EVENTS[event], fontsize=11.5, va="center"))
    fig.add(fig.fig.text(0.085, 0.562, event, fontsize=9, va="center", color=GREY, **TT))
    fig.add(fig.fig.text(0.99, 0.562, f"GRU gave it {p[INDEX[event]]:.0%},  oracle {q[INDEX[event]]:.0%}",
                         fontsize=9.5, va="center", ha="right", color=GREY))
    shown = list(np.argsort(-p)[:BARS])
    if INDEX[event] not in shown:
        shown[-1] = INDEX[event]
    for y, k in enumerate(shown):
        actual = VOCAB[k] == event
        fig.add(fig.bars.barh(y, p[k], height=0.56, color=GRU, lw=0)[0])
        fig.add(fig.bars.barh(y, q[k], height=0.78, fill=False, edgecolor=INK, lw=0.8)[0])
        fig.add(fig.bars.text(-0.04, y, VOCAB[k], ha="right", va="center", fontsize=8,
                              color=INK if actual else GREY, **TT))
        mark = r"  $\leftarrow$ happened" if actual else ""
        fig.add(fig.bars.text(max(p[k], q[k]) + 0.03, y, f"{p[k]:.2f}{mark}", va="center", fontsize=8.5,
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
    durations = [0.3 if events[t] in QUICK else 2.2 if events[t] in SLOW else 0.7 for t in range(1, n + 1)]
    durations[-1] = 4.5
    return _merge(static, frames, durations)
