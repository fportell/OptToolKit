This script implements a **Summary Revision Tool** using Streamlit and OpenAI's GPT-4.1 models. It provides both a **web-based interface** and a **command-line interface (CLI)** for users to revise and improve the grammar, clarity, and style of English text summaries, with an emphasis on editorial guidelines and the option to use Canadian English conventions.

---

## Entry point code

```bash
/home/fernando/OpsToolKit/legacy_code/opstoolkit/src/grammar_check/summary_revision.py
```

## High-Level Purpose

- **Main Goal:**  
    To help users (such as public health professionals, researchers, or editors) quickly revise and polish English summaries or paragraphs, ensuring grammatical correctness, clarity, and adherence to specific editorial guidelines (including Canadian English if desired).

---

## Key Features

### 1. **Streamlit Web Application**

- **User Interface:**
    
    - Lets users select a language model (GPT-4.1 or GPT-4.1-mini).
    - Option to enforce Canadian English spelling and grammar.
    - Text area for inputting the summary to be revised.
    - Button to trigger revision using OpenAI's API.
    - Displays the revised text and highlights changes (additions in green, deletions in red/strikethrough).
    - Option to copy the revised text.
    - Provides model information and editing guidelines.
- **Editing Guidelines:**
    
    - Numbers: Use Arabic numerals.
    - Dates: Acceptable formats specified.
    - Foreign Words: Remove accents except for French.
    - Tense Usage: Detailed rules for English tenses.
    - These are included in the prompt to the language model to ensure consistent editorial output.
- **Model Selection:**
    
    - **GPT-4.1:** Highest quality, best for nuanced editing.
    - **GPT-4.1-mini:** Faster and cheaper, still high quality.
- **Canadian English Option:**
    
    - When enabled, instructs the model to use Canadian spelling and grammar conventions.
- **Change Highlighting:**
    
    - Uses Python's `difflib` to visually show what was changed between the original and revised text.

### 2. **Command-Line Interface (CLI)**

- If not run in a Streamlit context, the script offers a CLI mode.
- Users can select the model, choose Canadian English, and input paragraphs for revision.
- Revised text is printed to the terminal.

### 3. **OpenAI API Integration**

- Uses the OpenAI Python SDK to send the user's text and editorial instructions to the selected GPT-4.1 model.
- Handles API key loading from environment variables (`.env` file).

### 4. **Robust Error Handling**

- Checks for required packages and API keys.
- Provides user-friendly error messages if something is missing or goes wrong.

---

## How It Works

1. **Environment Setup:**  
    Loads the OpenAI API key from a `.env` file.
    
2. **Streamlit App Launch:**
    
    - Sets up the page and session state.
    - Presents the UI for model selection, Canadian English option, and text input.
    - On clicking "Revise Summary," sends the text and guidelines to OpenAI.
    - Receives and displays the revised text, with visual diff highlighting.
    - Allows users to copy the output.
3. **CLI Mode:**
    
    - Prompts the user for model choice and Canadian English preference.
    - Accepts multi-line input for the summary.
    - Sends the text to OpenAI and prints the revised version.

---

## Intended Use Cases

- **Editing public health or scientific summaries for reports, publications, or communications.**
- **Ensuring consistency in language, style, and grammar, especially for organizations with Canadian English standards.**
- **Quickly revising text for clarity and correctness using state-of-the-art AI models.**

---

## Summary

**In essence:**  
This script is a professional-grade tool for revising English summaries, leveraging OpenAI's GPT-4.1 models. It provides a user-friendly web interface (and a CLI fallback), enforces detailed editorial guidelines, supports Canadian English, and visually highlights all changes for easy review. It is ideal for anyone needing fast, high-quality editorial assistance for English text.
