# Operator notes

## Run the local tire-dumping demo on Windows

1. Install and open [Ollama for Windows](https://ollama.com/download/windows).
2. On GitHub, download **Code → Download ZIP** and extract it, or run `git pull` if you already cloned Melilo.
3. Open PowerShell in the extracted or cloned Melilo folder (the one containing README.md). Run:

```powershell
ollama pull olmo2:7b
.\examples\local-dumping\run-demo.ps1
```

The first command downloads the model once. The second prints the comparison in PowerShell. This demo needs no Python, database, API key, or training.

### If Windows blocks PowerShell scripts

Run `ollama run olmo2:7b` and paste the entire [prompt.txt](../examples/local-dumping/prompt.txt) into Ollama. See the [demo README](../examples/local-dumping/README.md) for multiline paste instructions and what a passing answer looks like.

For the full project rather than this demo, see [script commands](script_commands.md).
