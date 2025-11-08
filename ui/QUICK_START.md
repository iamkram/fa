# FA AI Assistant - Quick Start Guide

## 🚀 Getting Started (3 Steps)

### Step 1: Install Dependencies
```bash
cd /Users/markkenyon/fa-ai-system/ui
yarn install
```

### Step 2: Start Backend Server
In a separate terminal:
```bash
cd /Users/markkenyon/fa-ai-system/src/interactive/api
python fastapi_server.py
```
Backend should be running at: `http://localhost:8000`

### Step 3: Start UI
```bash
cd /Users/markkenyon/fa-ai-system/ui
yarn dev
# Or use the startup script:
./start.sh
```
UI will be available at: `http://localhost:3000`

---

## 📋 Requirements Checklist

- ✅ Node.js 18+ installed
- ✅ Yarn package manager installed
- ✅ Backend server running on port 8000
- ✅ LangSmith API key configured (already in .env.local)

---

## 🎯 What You Get

1. **Professional Chat Interface**
   - Clean, minimalist design
   - No icons, text-based labels
   - Compass logo in header

2. **Source Citations**
   - Citations displayed below AI responses
   - Clickable links to original sources
   - Metadata preview

3. **Feedback System**
   - Thumbs up/down buttons
   - Integrated with LangSmith
   - One-click submission

4. **LangSmith Monitoring**
   - All queries traced automatically
   - Feedback logged in dashboard
   - View at: https://smith.langchain.com/

---

## 🔧 Configuration

All settings in `/ui/.env.local`:

```env
# Backend URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# LangSmith
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=fa-ai-dev
LANGSMITH_TRACING_V2=true

# Default FA ID
NEXT_PUBLIC_DEFAULT_FA_ID=FA-001
```

---

## 📁 Key Files

- `app/page.tsx` - Main chat page
- `app/api/chat/route.ts` - Backend connection
- `app/api/feedback/route.ts` - LangSmith feedback
- `components/Chat.tsx` - Chat interface
- `components/Message.tsx` - Messages with citations
- `components/Feedback.tsx` - Thumbs up/down

---

## 🐛 Troubleshooting

**Backend not connecting?**
```bash
# Check backend is running
curl http://localhost:8000/health
```

**Port already in use?**
```bash
# Use different port
PORT=3001 yarn dev
```

**Dependencies issue?**
```bash
rm -rf node_modules
yarn install
```

---

## 📚 Full Documentation

See `README.md` for complete documentation.

See `/Users/markkenyon/fa-ai-system/UI_IMPLEMENTATION_SUMMARY.md` for implementation details.

---

**Ready to use!** 🎉
