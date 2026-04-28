//! `ail-rs` CLI — Phase-0 stub.
//!
//! Subcommands:
//! - `tokens FILE.ail` — print the token stream
//! - `parse FILE.ail`  — pretty-print the parsed Program (Debug format)

use std::env;
use std::fs;
use std::process::ExitCode;

use ail::{Lexer, Parser};

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let prog = args.first().map(String::as_str).unwrap_or("ail-rs");
    if args.len() < 2 {
        usage(prog);
        return ExitCode::from(2);
    }
    match args[1].as_str() {
        "tokens" => cmd_tokens(prog, &args),
        "parse" => cmd_parse(prog, &args),
        cmd => {
            eprintln!("{prog}: unknown subcommand {cmd:?}");
            usage(prog);
            ExitCode::from(2)
        }
    }
}

fn cmd_tokens(prog: &str, args: &[String]) -> ExitCode {
    if args.len() != 3 {
        usage(prog);
        return ExitCode::from(2);
    }
    let src = match fs::read_to_string(&args[2]) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("{prog}: read {}: {e}", args[2]);
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

fn cmd_parse(prog: &str, args: &[String]) -> ExitCode {
    if args.len() != 3 {
        usage(prog);
        return ExitCode::from(2);
    }
    let src = match fs::read_to_string(&args[2]) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("{prog}: read {}: {e}", args[2]);
            return ExitCode::from(1);
        }
    };
    let tokens = match Lexer::new(&src).tokenize() {
        Ok(t) => t,
        Err(e) => {
            eprintln!("{prog}: {e}");
            return ExitCode::from(1);
        }
    };
    let mut parser = Parser::new(tokens);
    match parser.parse_program() {
        Ok(p) => {
            println!("{p:#?}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("{prog}: {e}");
            ExitCode::from(1)
        }
    }
}

fn usage(prog: &str) {
    eprintln!("usage:");
    eprintln!("  {prog} tokens FILE.ail   # dump token stream");
    eprintln!("  {prog} parse  FILE.ail   # dump parsed Program AST");
}
