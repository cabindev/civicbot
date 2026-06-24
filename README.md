# CivicSpace Messenger Bot

A Python [Microsoft Bot Framework](https://dev.botframework.com/) bot that uses
**Google Gemini** as its AI brain. It receives messages through Azure Bot
Service (connected to the **Facebook Messenger** channel) and replies in Thai on
behalf of CivicSpace, a Thai NGO focused on civic engagement and public space.

## Architecture

```
Facebook Messenger ──► Azure Bot Service ──► /api/messages (aiohttp) ──► Gemini
```

- `app.py` — aiohttp server, Bot Framework adapter, `/api/messages` endpoint.
- `bot.py` — `CivicSpaceBot`, handles activities and per-conversation history.
- `gemini_client.py` — async wrapper over `google-generativeai`.
- `config.py` — environment-driven configuration + system prompt.

The bot keeps the **last 10 turns** of each conversation in memory for context.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then fill in the values
python app.py          # serves on http://localhost:3978/api/messages
```

Test locally with the [Bot Framework Emulator](https://aka.ms/botframework-emulator),
pointing it at `http://localhost:3978/api/messages`.

## Required environment variables

| Variable                  | Description                                       |
| ------------------------- | ------------------------------------------------- |
| `MICROSOFT_APP_ID`        | App (client) ID of the Azure Bot registration     |
| `MICROSOFT_APP_PASSWORD`  | Client secret for the bot registration            |
| `MICROSOFT_APP_TYPE`      | `MultiTenant` (default), `SingleTenant`, or MSI   |
| `MICROSOFT_APP_TENANTID`  | Tenant ID (only for `SingleTenant`)               |
| `GEMINI_API_KEY`          | Google AI Studio API key                          |
| `GEMINI_MODEL`            | Optional, defaults to `gemini-1.5-flash`          |
| `PORT`                    | Optional, defaults to `3978`                      |

## Deploy to Azure App Service

1. Create a Linux App Service (Python 3.11) and an Azure Bot resource.
2. Set the messaging endpoint of the Azure Bot to
   `https://<your-app>.azurewebsites.net/api/messages`.
3. Add the environment variables above under **App Service → Configuration**.
4. Set the **Startup Command** (App Service → Configuration → General settings):

   ```
   python -m aiohttp.web -H 0.0.0.0 -P 8000 app:init_func
   ```

   Azure injects `PORT`; App Service expects the app on `8000` by default, so
   either match it above or set the `PORT` app setting accordingly. The included
   `Procfile` runs the same factory.
5. Deploy (`az webapp up`, GitHub Actions, or zip deploy).
6. In the Azure Bot resource, add the **Facebook** channel and connect your
   Facebook Page / Messenger app.

# civicbot
