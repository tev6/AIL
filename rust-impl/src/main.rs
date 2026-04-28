//! `ail-rs` CLI — Phase-0 stub.
//!
//! Subcommands:
//! - `tokens FILE.ail`            — print the token stream
//! - `parse FILE.ail`             — pretty-print the parsed Program (Debug)
//! - `run FILE.ail [INPUT]`       — execute the entry block, print final value

use std::env;
use std::fs;
use std::process::ExitCode;

use ail::{Evaluator, Lexer, Parser};

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
        "run" => cmd_run(prog, &args),
        cmd => {
            eprintln!("{prog}: unknown subcommand {cmd:?}");
            usage(prog);
            ExitCode::from(2)
        }
    }
}

fn read_src(prog: &str, path: &str) -> Result<String, ExitCode> {
    fs::read_to_string(path).map_err(|e| {
        eprintln!("{prog}: read {path}: {e}");
        ExitCode::from(1)
    })
}

fn cmd_tokens(prog: &str, args: &[String]) -> ExitCode {
    if args.len() != 3 {
        usage(prog);
        return ExitCode::from(2);
    }
    let src = match read_src(prog, &args[2]) {
        Ok(s) => s,
        Err(e) => return e,
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
    let src = match read_src(prog, &args[2]) {
        Ok(s) => s,
        Err(e) => return e,
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

fn cmd_run(prog: &str, args: &[String]) -> ExitCode {
    if args.len() < 3 {
        usage(prog);
        return ExitCode::from(2);
    }
    let input = if args.len() >= 4 { args[3].as_str() } else { "" };
    let src = match read_src(prog, &args[2]) {
        Ok(s) => s,
        Err(e) => return e,
    };
    let program = match ail::parse(&src) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("{prog}: {e}");
            return ExitCode::from(1);
        }
    };
    let evaluator = Evaluator::new(&program);
    match evaluator.run(input) {
        Ok(v) => {
            println!("{v}");
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
    eprintln!("  {prog} tokens FILE.ail              # dump token stream");
    eprintln!("  {prog} parse  FILE.ail              # dump parsed Program AST");
    eprintln!("  {prog} run    FILE.ail [INPUT]      # execute and print final value");
}
