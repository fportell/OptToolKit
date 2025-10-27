This code is a **Streamlit web application** designed to automate the extraction, normalization, and categorization of daily report data from uploaded HTML files, and export the results as a macro-enabled Excel workbook for downstream analysis and reporting.

---
## Entry point code

```bash
/home/fernando/OpsToolKit/legacy_code/opstoolkit/src/daily_report/daily_report.py
```

## High-Level Overview

1. **User Authentication**:  
    The app checks user authentication before proceeding, ensuring only authorized users can access its features.
    
2. **File Upload & Preprocessing**:  
    Users upload a daily report in HTML format. The app processes the HTML to:
    
    - Replace Microsoft Safe Links with real URLs.
    - Sanitize problematic Unicode characters for compatibility.
3. **Data Extraction via OpenAI**:  
    The cleaned HTML is sent to an OpenAI GPT model (gpt-4.1), which parses the report and returns a structured JSON representation of the entries.
    
4. **Data Transformation**:  
    The JSON is converted into a Pandas DataFrame, with columns for entry number, hazards, date, locations, summary, references, section, and program areas.
    
5. **Program Area Tagging (OpenAI)**:  
    For each entry, the app uses OpenAI again to assign relevant "program area" tags based on the location and summary, using a specialized prompt and a Pydantic model for structured output.
    
6. **Hazard Normalization**:  
    Hazards are normalized using a transformer-based semantic matching model (with fuzzy matching fallback), ensuring consistent hazard naming across entries.
    
7. **Excel Export with Macros**:  
    The processed data is exported to an in-memory Excel `.xlsm` file with two worksheets:
    
    - **Flags_and_Tags**: For summary and tagging, with Excel-formatted hyperlinks.
    - **DR_tracker_PBI**: For detailed tracking, including normalized hazards.
    - The file includes an embedded VBA macro (from `vbaProject.bin`).
8. **User Download**:  
    The user can download the generated Excel file directly from the app.
    

---

## Key Features & Functions

- **replace_safe_links**:  
    Decodes Microsoft Safe Links in HTML anchor tags and removes text fragments that can break Excel hyperlinks.
    
- **sanitize_html_text**:  
    Replaces problematic Unicode punctuation with ASCII equivalents for compatibility.
    
- **json_to_dataframe**:  
    Converts the OpenAI-parsed JSON into a structured DataFrame, handling lists, missing values, and reference extraction.
    
- **transform_dataframe4flag_and_tags**:  
    Prepares a DataFrame for the "Flags_and_Tags" worksheet, formatting references as Excel hyperlinks.
    
- **add_normalized_hazard_column**:  
    Adds a column with normalized hazard names using semantic and fuzzy matching, with robust error handling.
    
- **get_program_area_list**:  
    Uses OpenAI to assign program area tags to each entry, based on location and summary, using a Pydantic model for structured output.
    
- **save_to_excel**:  
    Writes the two DataFrames to an in-memory Excel file, embedding a VBA macro for further automation.
    
- **Streamlit UI**:  
    Provides a user interface for uploading files, viewing extracted content, and downloading the processed Excel file.
    

---

## Typical Workflow

1. **User logs in** (authentication check).
2. **User uploads a daily report HTML file**.
3. **App processes and sanitizes the HTML**.
4. **App sends the HTML to OpenAI for parsing**.
5. **App displays the extracted JSON for review**.
6. **App builds a DataFrame and tags program areas using OpenAI**.
7. **App normalizes hazard names**.
8. **App generates and offers a downloadable Excel file** with all processed data and macros.

---

## Intended Use Case

This tool is designed for organizations (such as public health agencies) that need to:

- Rapidly extract structured data from narrative daily reports.
- Normalize and categorize hazards for consistent tracking.
- Tag entries with relevant program areas for reporting and analytics.
- Export results in a format ready for further analysis (e.g., Power BI) and with built-in Excel automation.

---

**In summary:**  
This code automates the ingestion, parsing, normalization, tagging, and export of daily report data, leveraging OpenAI for both data extraction and intelligent tagging, and delivers the results in a macro-enabled Excel workbook for end users.
