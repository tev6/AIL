//! `ail-rs` CLI.
//!
//! Subcommands:
//! - `tokens FILE.ail`                       — print the token stream
//! - `parse FILE.ail`                        — pretty-print the parsed Program (Debug)
//! - `run [--adapter NAME] FILE.ail [INPUT]` — execute the entry block

use std::env;
use std::fs;
use std::process::ExitCode;

use ail::{AnthropicAdapter, Evaluator, Lexer, Parser};

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
    // ail-rs run [--adapter NAME] FILE.ail [INPUT]
    let mut adapter_name: Option<String> = None;
    let mut positional: Vec<&str> = Vec::new();
    let mut i = 2;
    while i < args.len() {
        let a = args[i].as_str();
        if a == "--adapter" {
            if i + 1 >= args.len() {
                eprintln!("{prog}: --adapter requires a value");
                return ExitCode::from(2);
            }
            adapter_name = Some(args[i + 1].clone());
            i += 2;
            continue;
        }
        positional.push(a);
        i += 1;
    }
    if positional.is_empty() {
        usage(prog);
        return ExitCode::from(2);
    }
    let path = positional[0];
    let input = positional.get(1).copied().unwrap_or("");
    let src = match read_src(prog, path) {
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

    // Adapter: explicit `--adapter` wins. Otherwise, auto-enable Anthropic
    // when the program declares an `intent` AND ANTHROPIC_API_KEY is set —
    // this mirrors Python's "the intent works if you have a key" UX so a
    // user who follows the install one-liner doesn't have to learn flags.
    let resolved_adapter = adapter_name.or_else(|| {
        if !program.intents.is_empty() && std::env::var_os("ANTHROPIC_API_KEY").is_some() {
            Some("anthropic".into())
        } else {
            None
        }
    });

    let mut evaluator = Evaluator::new(&program);
    if let Some(name) = resolved_adapter {
        match name.as_str() {
            "anthropic" => match AnthropicAdapter::from_env() {
                Ok(a) => evaluator.adapter = Some(Box::new(a)),
                Err(e) => {
                    eprintln!("{prog}: {e}");
                    return ExitCode::from(1);
                }
            },
            other => {
                eprintln!("{prog}: unknown --adapter {other:?} (supported: anthropic)");
                return ExitCode::from(2);
            }
        }
    }

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
    eprintln!("  {prog} tokens FILE.ail                       # dump token stream");
    eprintln!("  {prog} parse  FILE.ail                       # dump parsed Program AST");
    eprintln!("  {prog} run [--adapter NAME] FILE.ail [INPUT] # execute and print final value");
    eprintln!();
    eprintln!("Adapters:");
    eprintln!("  --adapter anthropic    Anthropic Messages API (needs ANTHROPIC_API_KEY)");
    eprintln!("                         Auto-enabled when a program declares `intent`");
    eprintln!("                         and ANTHROPIC_API_KEY is set.");
}
