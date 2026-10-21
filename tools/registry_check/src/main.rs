//! Reads one assembly per line from stdin, as `gear=dep,dep;gear=;...`, registers every gear with the
//! real `toolkit::registry::RegistryBuilder`, and prints what `build_topo_sorted` says: `ok`, or the
//! error variant name. `tools/crosscheck_registry.py` compares the answers with Nextgear's own check.

use std::io::{self, BufRead, Write};
use std::sync::Arc;

use toolkit::registry::{RegistryBuilder, RegistryError};

struct Stub;

#[toolkit::async_trait]
impl toolkit::contracts::Gear for Stub {
    async fn init(&self, _ctx: &toolkit::GearCtx) -> toolkit::Result<()> {
        Ok(())
    }
}

fn leak(s: &str) -> &'static str {
    Box::leak(s.to_owned().into_boxed_str())
}

fn main() {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    for line in io::stdin().lock().lines() {
        let line = line.expect("stdin");
        let mut builder = RegistryBuilder::default();
        for entry in line.split(';').filter(|e| !e.is_empty()) {
            let (name, deps) = entry.split_once('=').expect("gear=deps");
            let deps: Vec<&'static str> = deps.split(',').filter(|d| !d.is_empty()).map(leak).collect();
            builder.register_core_with_meta(leak(name), Box::leak(deps.into_boxed_slice()), Arc::new(Stub));
        }
        let verdict = match builder.build_topo_sorted() {
            Ok(_) => "ok".to_owned(),
            Err(RegistryError::UnknownDependency { .. }) => "unknown-dependency".to_owned(),
            Err(RegistryError::CycleDetected { .. }) => "cycle".to_owned(),
            Err(other) => format!("other: {other}"),
        };
        writeln!(out, "{verdict}").expect("stdout");
    }
}
