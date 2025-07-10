# Korean Language Problem Extraction and Classification Service

This project aims to automatically extract and classify Korean language problems from documents using the LayoutLMv3 model.

## Project Structure

-   `src/`: Main source code for the service.
-   `data/`: Datasets for training and evaluation.
-   `models/`: Trained models.
-   `notebooks/`: Jupyter notebooks for experimentation.
-   `tests/`: Tests for the codebase.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Run the service:
    ```bash
    uvicorn src.main:app --reload
    ```
