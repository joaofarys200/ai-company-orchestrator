//! Native Rust Knowledge & Obsidian Vault subsystem.
//!
//! Replaces the legacy Python `Knowledge` domain worker for vault note CRUD,
//! strict path containment, atomic CAS backups & rollback, 4-category calibrated
//! quality scoring, bounded improvement batches, and two-pass graph diagnostics.

pub mod dispatch;
pub mod graph_engine;
pub mod vault;
