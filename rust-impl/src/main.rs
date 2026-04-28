//! `ail-rs` CLI — Phase-0 stub.
//!
//! Subcommands:
//! - `tokens FILE.ail` — print the token stream (debug aid for spec parity).

use std::env;
use std::fs;
use std::process::ExitCode;

use ail::Lexer;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let prog = args.first().map(String::as_str).unwrap_or("ail-rs");
    if args.len() < 2 {
        usage(prog);
        return ExitCode::from(2);
    }
    match args[1].as_str() {
        "tokens" => {
            if args.len() != 3 {
                usage(prog);
                return ExitCode::from(2);
            }
            let path = &args[2];
            let src = match fs::read_to_string(path) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("{prog}: read {path}: {e}");
                    return ExitCode::from(1);
                }
            };
            match Lexer::new(&src).tokenize() {
                Ok(toks) => {
                    for t in toks {
                        println!("{t}");
                    }
                    ExitCode::SUCCESS
                }
                Err(e) => {
                    eprintln!("{prog}: {e}");
                    ExitCode::from(1)
                }
            }
        }
        cmd => {
            eprintln!("{prog}: unknown subcommand {cmd:?}");
            usage(prog);
            ExitCode::from(2)
        }
    }
}

fn usage(prog: &str) {
    eprintln!("usage:");
    eprintln!("  {prog} tokens FILE.ail   # dump token stream");
}
