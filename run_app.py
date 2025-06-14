from dotenv import load_dotenv
import os
import streamlit.web.cli as stcli
import sys

load_dotenv()  # Load .env variables

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", "main.py"]
    sys.exit(stcli.main())