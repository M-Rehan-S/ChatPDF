# DocChat — RAG PDF Chatbot UI

A clean, dark-themed chat interface for a Retrieval-Augmented Generation (RAG) PDF chatbot, built to drop straight into a Flask backend.

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.x+-lightgrey?style=flat-square&logo=flask)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Features

- **PDF Upload** — drag-and-drop or click to upload multiple PDFs with an animated progress bar
- **Document Sidebar** — lists all indexed documents with page count, file size, and per-document removal
- **Configurable Retrieval** — choose top-k chunks (3 / 5 / 8 / 10) per query from the UI
- **Multi-turn Chat** — sends the last 10 conversation turns with every request for context-aware answers
- **Source Citations** — each answer displays which document (and page) the information came from
- **Typing Indicator** — animated dots while the backend is processing
- **Status Bar** — live status indicator (Ready / Uploading / Searching / Error)
- **Keyboard Shortcuts** — `Enter` to send, `Shift+Enter` for a new line

---

## Project Structure

```
your-project/
├── app.py                  # Flask backend
├── pyproject.toml          # Project dependencies (managed with uv)
├── templates/
│   └── index.html          # This UI file
├── static/                 # (optional) for any additional assets
└── README.md
```

---

## Setup

### 1. Install dependencies

Dependencies are declared in `pyproject.toml` and managed with [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

### 2. Run the app

```bash
uv run python app.py
```

Or if you have a run script defined in `pyproject.toml`:

```bash
uv run flask run
```

### 3. Open the UI

Navigate to `http://localhost:5000` in your browser.

---

## Placing the UI

Put `index.html` inside your Flask project's `templates/` folder and serve it from the `GET /` route.

---

## API Contract

The UI communicates with five endpoints on your Flask backend. Below is the exact shape of each request and expected response.

---

### `GET /`
Serves the chat interface.

---

### `POST /upload`

Receives a PDF file, indexes it, and returns metadata.

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | File | The PDF file to upload |

**Response:**
```json
{
  "id": "doc_001",
  "name": "report.pdf",
  "pages": 12,
  "chunks": 48
}
```

---

### `POST /chat`

Accepts a question with conversation history and returns a grounded answer with sources.

**Request body:**
```json
{
  "question": "What are the key findings?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "top_k": 5
}
```

| Field | Type | Description |
|---|---|---|
| `question` | string | The user's query |
| `history` | array | Last up to 10 turns of conversation |
| `top_k` | integer | Number of chunks to retrieve (3, 5, 8, or 10) |

**Response:**
```json
{
  "answer": "The key findings include...",
  "sources": [
    { "doc_name": "report.pdf", "page": 4 },
    { "doc_name": "appendix.pdf", "page": 11 }
  ]
}
```

---

### `DELETE /document/<id>`

Removes a single document from the index.

**Response:**
```json
{ "deleted": "doc_001" }
```

---

### `POST /clear`

Clears all documents and resets the index.

**Response:**
```json
{ "status": "cleared" }
```

---

## Customisation

| What | Where in `index.html` |
|---|---|
| Change top-k options | `<select id="top-k">` |
| Adjust conversation history window | `state.chatHistory.slice(-10)` |
| Modify the color palette | CSS `:root` variables at the top of `<style>` |

---

## License

GNU.
