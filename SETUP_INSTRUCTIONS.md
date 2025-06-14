# 🚀 Application Setup Instructions

Follow these steps to set up and run the application successfully.

## 📋 Prerequisites

- Python 3.7 or higher installed
- Git (optional, for cloning)

---

## 🔧 Step 1: Project Setup

1. **Download/Clone the project** to your local machine
2. **Open terminal/command prompt** and navigate to the project folder
   ```bash
   cd path/to/your/project
   ```

---

## 🔑 Step 2: Configure API Keys

### A. Update the .env file

1. **Locate the `.env` file** in the project root directory
2. **Open `.env` file** in any text editor (Notepad, VS Code, etc.)
3. **Replace the placeholder values** with your actual API keys:

```env
# BEFORE (example placeholders):
OPENAI_API_KEY=your_openai_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# AFTER (your actual values):
OPENAI_API_KEY=sk-proj-abc123...your_actual_key
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...your_actual_key
GOOGLE_CLIENT_ID=123456789-abc...your_actual_client_id
GOOGLE_CLIENT_SECRET=GOCSPX-abc123...your_actual_secret
```

### B. Update main.py (if applicable)

1. **Open `main.py`** in a text editor
2. **Find any lines** containing `@YOUR_API_KEY` or similar placeholders
3. **Replace them** with your actual API keys:

```python
# BEFORE:
api_key = "@YOUR_API_KEY"
openai_key = "@YOUR_OPENAI_KEY"

# AFTER:
api_key = "your_actual_api_key_here"
openai_key = "sk-proj-your_actual_openai_key"
```

> ⚠️ **Important**: Make sure there are no extra spaces or quotes around your API keys in the .env file!

---

## 🔍 Step 3: Get Your API Keys

### OpenAI API Key
1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in to your OpenAI account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-proj-` or `sk-`)

### Supabase Keys
1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Sign in and select your project
3. Go to Settings → API
4. Copy the "URL" and "anon public" key

### Google OAuth (if needed)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Go to Credentials → Create Credentials → OAuth client ID
5. Copy Client ID and Client Secret

---

## 🐍 Step 4: Install Dependencies

### Windows:
```batch
# Activate virtual environment
venv_ayu1.5\Scripts\activate

# Install required packages
pip install python-dotenv streamlit openai supabase
```

### Linux/Mac:
```bash
# Activate virtual environment
source venv_ayu1.5/bin/activate

# Install required packages
pip install python-dotenv streamlit openai supabase
```

---

## ✅ Step 5: Test Configuration

Run this test to verify your setup:

```bash
# Make sure virtual environment is activated
python check_env.py
```

You should see:
```
✅ OPENAI_API_KEY: SET
✅ SUPABASE_URL: SET  
✅ SUPABASE_KEY: SET
✅ Configuration loaded successfully!
```

---

## 🚀 Step 6: Run the Application

### For Streamlit apps:
```bash
streamlit run main.py
```

### For regular Python apps:
```bash
python main.py
```

Your application should now start successfully!

---

## 🛠️ Troubleshooting

### ❌ "Missing required environment variables" error:
- Check that your `.env` file is in the project root (same level as `venv_ayu1.5`)
- Verify there are no extra spaces around the `=` in your `.env` file
- Make sure you saved the `.env` file after editing
- Run `python check_env.py` to debug

### ❌ "Module not found" errors:
- Make sure your virtual environment is activated
- Install missing packages: `pip install package_name`

### ❌ API key errors:
- Verify your API keys are valid and active
- Check for typos in your keys
- Ensure you have sufficient credits/quota

### ❌ Permission errors:
- Make sure you have write permissions in the project folder
- Try running terminal as administrator (Windows) or with `sudo` (Linux/Mac)

---

## 📁 Expected File Structure

```
your_project/
├── venv_ayu1.5/              # Virtual environment
├── core/
│   └── config_manager.py     # Configuration manager
├── .env                      # Your API keys (EDIT THIS)
├── .gitignore               # Git ignore file
├── main.py                  # Main application (CHECK FOR @YOUR_API_KEY)
├── check_env.py             # Test script
├── SETUP_INSTRUCTIONS.md    # This file
└── requirements.txt         # Dependencies list
```

---

## 🔐 Security Notes

- **Never commit** your `.env` file to Git/GitHub
- **Keep your API keys private** - don't share them
- **Use environment variables** instead of hardcoding keys
- **Regenerate keys** if you accidentally expose them

---

## 💬 Need Help?

If you encounter issues:

1. **Read the error message carefully**
2. **Check the troubleshooting section above**
3. **Run the debug script**: `python check_env.py`
4. **Verify your file structure matches the expected layout**

---

## ✨ Quick Start Checklist

- [ ] Downloaded/cloned the project
- [ ] Created/obtained all required API keys
- [ ] Updated `.env` file with actual API keys
- [ ] Checked `main.py` for `@YOUR_API_KEY` placeholders
- [ ] Activated virtual environment
- [ ] Installed dependencies with `pip install`
- [ ] Ran `python check_env.py` successfully
- [ ] Started the application with `streamlit run main.py` or `python main.py`

**🎉 You're all set! Enjoy using the application!**