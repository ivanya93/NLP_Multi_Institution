# NLP Multi-Institution Analytics App

## Overview

The **NLP Multi-Institution Analytics App** is an interactive data analysis and decision-support tool designed to make it easier to explore and compare financial and operational information from multiple social institutions.

The underlying information comes from PDF documents, which can be difficult to analyze consistently because data may be presented in different formats and Social Security funding can be recorded in different ways.

This application transforms that information into an interactive dashboard where users can:

* Explore key financial and operational KPIs.
* Filter data by year, institution, activity, social response, and region.
* Compare performance across social responses and geographic regions.
* Explore individual institutions.
* Identify social responses that may be underfunded or operating at a loss.
* Ask questions about the data using an AI Assistant.
* Export filtered data for further analysis.

The main goal is to turn complex and fragmented information into a format that supports **faster analysis, comparison, and decision-making**.

---

## Access the App

🔗 **Streamlit App:**
https://nlpmultiinstitution-4shb4sdxyeprkspt3tgrpz.streamlit.app/

---

# How the App Works

The application can be understood as having **two main layers**:

### 1. Sidebar — "What am I looking at?"

The sidebar controls the data being analyzed.

### 2. Tabs — "How do I want to see it?"

The different tabs provide different ways to analyze the selected data, from a high-level overview to detailed institution-level information.

The key idea is:

> **The sidebar defines the data scope, and the tabs define the perspective.**

Any filters selected in the sidebar are applied across the application, so the different views remain consistent.

---

# 1. Sidebar: Data Controls

The sidebar is the starting point for exploring the application.

### Language

Users can switch between:

* 🇬🇧 English
* 🇵🇹 Portuguese

The application interface updates to the selected language.

### Social Security Funding Method

The app provides two options for calculating or interpreting **Social Security funding per beneficiary**.

This is necessary because the original PDF sources do not always record this funding consistently. Depending on the interpretation used, the resulting values can differ.

Users can therefore select the methodology that best fits their analysis.

### Filters

The data can be filtered by:

* **Year**
* **Institution**
* **Activity Group**

  * Elderly care
  * Childcare
* **Social Response**

  * Creche
  * ERPI
  * Centro de Dia
  * And others
* **Region**

The filters work together using an **AND logic**.

For example, a user could select:

> 2024 + a specific region + elderly care + ERPI

The application will then display only the records matching **all** of those conditions.

### Quick Counters

The sidebar also provides three quick indicators showing the size of the current selection:

* Number of institutions
* Number of records
* Number of beneficiaries

### Data Export

Users can download the currently filtered data as a **CSV file** for additional analysis outside the application.

---

# 2. Overview

The **Overview** tab provides a high-level summary of the selected data.

It is designed to answer:

> **"What is the overall situation?"**

The page includes key performance indicators such as:

* Median cost
* Median funding
* Coverage compared with the **50% target**
* Percentage of social responses reaching the target
* EBITDA

The dashboard also provides visual comparisons of:

* Social responses and their distance from the funding target.
* Costs, funding, and fees across activity groups.
* The percentage of records that are currently operating at a loss.

This is the best place to start when you want to quickly understand the overall financial situation before exploring the details.

---

# 3. By Social Response

The **By Social Response** tab allows users to compare different types of social responses.

Examples include:

* Creche
* ERPI
* Centro de Dia
* Other social responses

Users can select a KPI from a dropdown menu and compare its performance across different social responses.

The results are displayed through:

* Interactive charts
* Summary statistics

The summary statistics include:

* Median
* Mean
* Minimum
* Maximum

This view helps answer questions such as:

> Which social responses have the highest costs?

> Which social responses receive the highest funding?

> Which responses are closest to or furthest from the funding target?

---

# 4. By Region

The **By Region** tab follows a similar approach but focuses on geographical differences.

Users can select a KPI and compare results across different regions.

The results are presented using:

* Visual comparisons
* Summary statistics

This makes it easier to identify geographical patterns and understand whether financial performance differs between regions.

For example, users can investigate whether certain regions have:

* Higher costs
* Higher funding
* Better coverage
* Higher or lower EBITDA

---

# 5. Institution Explorer

The **Institution Explorer** provides a more detailed view of an individual institution.

Users can select an anonymized institution and explore:

* Institution region
* Year
* Social responses provided by the institution
* Financial and operational KPIs for each social response

This view moves from the broader analysis to the individual institution level.

It is useful when the goal is to understand the specific situation of one organization rather than comparing the entire dataset.

The information can also be exported for further analysis.

---

# 6. AI Assistant

The **AI Assistant** allows users to interact with the data using natural language.

Instead of manually navigating through multiple charts and tables, users can ask questions about the selected data.

For example:

> "Which social responses are below the funding target?"

> "Which regions have the highest median costs?"

> "Which social responses are currently losing money?"

The assistant has access to the application's data and tools, allowing it to retrieve information from the filtered dataset rather than simply generating a generic response.

The AI Assistant can also help create **negotiation talking points** based on the analysis.

Users can download the conversation for future reference.

### Important

The AI Assistant should be treated as a **decision-support tool**. Its responses should always be checked against the underlying data, especially when the information is being used for important financial or operational decisions.

---

# 7. Data

The **Data** tab provides direct access to the underlying information.

It is intended for users who want to work directly with the numbers rather than only using visualizations.

The application provides:

* The filtered KPI dataset
* The complete extracted dataset

This section is useful for:

* Checking the underlying values.
* Validating the visualizations.
* Performing additional analysis.
* Exporting data for use in other tools.

---

# Example Workflow

A typical analysis could follow these steps:

### Step 1 — Define the scope

Use the sidebar to select:

* Year
* Region
* Activity group
* Institution
* Social response

### Step 2 — Start with the Overview

Check the main KPIs to understand the overall financial situation.

### Step 3 — Compare Social Responses

Go to **By Social Response** to identify which services have stronger or weaker financial performance.

### Step 4 — Compare Regions

Use **By Region** to identify geographical differences.

### Step 5 — Investigate an Institution

Use **Institution Explorer** to understand the situation of a specific organization.

### Step 6 — Ask the AI Assistant

Use natural language to quickly investigate a specific question or summarize findings.

### Step 7 — Export the Data

Download the relevant filtered dataset for additional analysis or reporting.

---

# Main Value of the Application

The application brings together several analytical perspectives in one place.

Instead of manually reviewing multiple PDF documents and comparing information across different sources, users can interactively explore the data.

The application helps answer three main questions:

### 1. What is happening?

The **Overview** provides a high-level picture of the current situation.

### 2. Where are the differences?

The **By Social Response** and **By Region** tabs allow users to identify patterns and compare performance.

### 3. Why is it happening?

The **Institution Explorer**, **Data** tab, and **AI Assistant** allow users to investigate specific cases and ask more targeted questions.

---

# Application Structure

```text
                    ┌─────────────────────┐
                    │       SIDEBAR       │
                    │  "What am I seeing?"│
                    └──────────┬──────────┘
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
             ▼                                   ▼
    Data Filters & Scope                  Data Export
             │
             ▼
    ┌────────────────────────────────────────────┐
    │                  ANALYSIS                   │
    ├────────────┬────────────┬───────────┬──────┤
    │  Overview  │  Social    │  Region   │Institution
    │            │  Response  │           │Explorer
    ├────────────┴────────────┴───────────┴──────┤
    │               AI Assistant                  │
    │        "Ask the data in natural language"   │
    ├─────────────────────────────────────────────┤
    │                    Data                     │
    │           "Access the underlying data"      │
    └─────────────────────────────────────────────┘
```

---

# Quick Summary

| Section                  | Main Purpose                                     |
| ------------------------ | ------------------------------------------------ |
| **Sidebar**              | Define the data scope using filters              |
| **Overview**             | Understand the overall situation                 |
| **By Social Response**   | Compare different social services                |
| **By Region**            | Compare geographical performance                 |
| **Institution Explorer** | Analyze one institution in detail                |
| **AI Assistant**         | Ask questions about the data in natural language |
| **Data**                 | Explore and export the underlying data           |

---

## Final Takeaway

The application is designed to make complex institutional data easier to explore and understand.

The central concept is simple:

> **The sidebar answers "What am I looking at?"**
> **The tabs answer "How do I want to see it?"**

Users can move from a **high-level overview**, to **comparisons by social response and region**, to **individual institution analysis**, and finally use the **AI Assistant** as a shortcut to ask questions directly about the data.

Together, these features provide a single interactive environment for exploring performance, identifying potential funding gaps, and supporting data-driven decision-making.
