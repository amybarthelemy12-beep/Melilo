# Local Melilo pilot: What happened after free tire drop-offs?

Try one question against two counties' public records. This is a comparison and citation test using stock OLMo 2 7B, not a trained Melilo checkpoint or the production pipeline. It does not crawl records, connect to a database, use a cloud API, or train a model.

## Run on Windows

1. Install [Ollama for Windows](https://ollama.com/download/windows) and open it. Allow roughly 10 GB of free disk space for the application and model. You'll need internet for those first downloads.
2. Download the repository as a ZIP (GitHub **Code → Download ZIP**) and extract it, or pull the latest changes if you already cloned it. In File Explorer, open `examples\local-dumping` inside the extracted folder. Type `powershell` into the address bar and press Enter.
3. Run these commands:

   ```powershell
   ollama pull olmo2:7b
   .\run-demo.ps1
   ```

   If Windows blocks scripts, use the manual route below rather than changing your execution policy.

### Manual route

Run `ollama run olmo2:7b`, open [prompt.txt](prompt.txt), and paste the entire file as one message. If the terminal splits it into separate messages, type three double quotes, press Enter, paste the file, then type three double quotes on their own line and press Enter. Use `/bye` to quit.

## What a passing answer says

- **Los Angeles County:** nine events, 410 tons accepted from the public in 2024; **separately**, 167 tons of illegally dumped tires recovered by road crews.
- **Pinellas County:** 861 tires accepted at the April 18, 2026 event; 1,082 at a separate 2025 event, if mentioned. Those are tire counts, not tons.
- Both show people used free disposal. The records do not establish whether dumping went down in either county or which approach worked better. The answer cites the official records and doesn't invent numbers, dollar costs, or laws.

The included facts are original summaries with links, not copies of county documents or additions to the training corpus. The model can still get facts wrong; use the above criteria to score its answer before expanding the pilot.
