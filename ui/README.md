# FA AI Assistant - User Interface

A clean, professional Next.js UI for the FA AI System, designed specifically for financial advisors.

## Features

- **Clean, Professional Design**: Minimalist interface with no icons, focused on clarity and professionalism
- **Real-time Chat**: Interactive chat interface powered by the FA AI backend
- **Source Citations**: Display and link to source data for transparency and verification
- **Feedback System**: Thumbs up/down feedback integrated with LangSmith for continuous improvement
- **LangSmith Tracing**: All API calls are traced in LangSmith for monitoring and evaluation
- **Session Management**: Persistent conversation history per session
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Tech Stack

- **Framework**: Next.js 15 with App Router
- **UI Components**: Radix UI primitives with Tailwind CSS
- **AI SDK**: Vercel AI SDK for streaming chat
- **Backend Integration**: FastAPI server at `http://localhost:8123`
- **Monitoring**: LangSmith for tracing and feedback collection

## Prerequisites

- Node.js 18 or higher
- Yarn package manager
- FA AI Backend server running on `http://localhost:8123`

## Setup Instructions

### 1. Install Dependencies

```bash
cd ui
yarn install
```

### 2. Environment Configuration

The `.env.local` file is already configured with the necessary environment variables:

```env
# LangSmith Configuration
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=fa-ai-dev
LANGSMITH_TRACING_V2=true

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8123

# FA ID (can be overridden per session)
NEXT_PUBLIC_DEFAULT_FA_ID=FA-001
```

**Note**: These values are pre-configured to match your existing setup. No changes needed unless you want to use a different backend URL or FA ID.

### 3. Start the Development Server

```bash
yarn dev
```

The UI will be available at `http://localhost:3000`

### 4. Start the Backend Server

In a separate terminal, ensure the FA AI backend is running:

```bash
# From the fa-ai-system root directory
cd src/interactive/api
python fastapi_server.py
```

The backend should be running on `http://localhost:8123`

## Usage

1. **Open the UI**: Navigate to `http://localhost:3000` in your browser
2. **Start Chatting**: Type your question in the input field and press Send
3. **View Sources**: Source citations will appear below AI responses when available
4. **Provide Feedback**: Use the "Thumbs up" or "Thumbs down" buttons to rate responses
5. **Monitor in LangSmith**: All interactions are logged in LangSmith under the `fa-ai-dev` project

## Project Structure

```
ui/
├── app/
│   ├── api/
│   │   ├── chat/
│   │   │   └── route.ts          # Chat API route (connects to backend)
│   │   └── feedback/
│   │       └── route.ts          # Feedback API route (LangSmith integration)
│   ├── globals.css               # Global styles
│   ├── layout.tsx                # Root layout with logo and header
│   └── page.tsx                  # Main chat page
├── components/
│   ├── Chat.tsx                  # Main chat component
│   ├── Message.tsx               # Message bubble with sources
│   ├── Feedback.tsx              # Thumbs up/down component
│   └── ui/                       # Radix UI components
├── public/
│   └── images/
│       └── compass-logo.png      # FA AI logo
├── utils/
│   └── cn.ts                     # Utility functions
├── .env.local                    # Environment configuration
├── package.json                  # Dependencies
├── tailwind.config.js            # Tailwind CSS configuration
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # This file
```

## Key Components

### Chat Component (`components/Chat.tsx`)
- Main chat interface
- Manages conversation state
- Handles streaming responses
- Integrates with backend API

### Message Component (`components/Message.tsx`)
- Displays individual messages
- Shows source citations with links
- Integrates feedback component

### Feedback Component (`components/Feedback.tsx`)
- Thumbs up/down buttons
- Submits feedback to LangSmith
- Provides user confirmation

### Chat API Route (`app/api/chat/route.ts`)
- Proxies requests to FA AI backend
- Handles session management
- Returns sources in response headers
- Provides run IDs for feedback

### Feedback API Route (`app/api/feedback/route.ts`)
- Submits user feedback to LangSmith
- Associates feedback with specific runs
- Supports score and optional comments

## API Integration

### Backend Request Format

```typescript
{
  "fa_id": "FA-001",
  "session_id": "unique-session-id",
  "query_text": "User's question",
  "query_type": "chat",
  "context": {}
}
```

### Backend Response Format

```typescript
{
  "query_id": "unique-query-id",
  "response_text": "AI response text",
  "response_tier": "tier1",
  "processing_time_ms": 1234,
  "guardrail_status": "passed",
  "citations": [
    {
      "pageContent": "Source text...",
      "metadata": {
        "source": "Source name",
        "url": "https://source-url.com"
      }
    }
  ],
  "pii_flags": []
}
```

## LangSmith Integration

### Tracing
- All chat interactions are traced in LangSmith
- Run IDs are captured from backend responses
- Traces include query text, response, and timing information

### Feedback
- User feedback (thumbs up/down) is sent to LangSmith
- Feedback is associated with specific runs via run ID
- Accessible in LangSmith dashboard for evaluation

To view traces and feedback:
1. Go to [LangSmith](https://smith.langchain.com/)
2. Navigate to the `fa-ai-dev` project
3. View runs and associated feedback

## Building for Production

```bash
# Build the application
yarn build

# Start the production server
yarn start
```

## Customization

### Change Logo
Replace `public/images/compass-logo.png` with your own logo (recommended size: 40x40px or higher)

### Modify Color Scheme
Edit `app/globals.css` to change the color palette. The current scheme uses professional blues and grays suitable for financial services.

### Adjust Max Message Width
In `components/Chat.tsx`, modify the `max-w-[900px]` class to change the maximum width of messages.

### Change Default FA ID
Update `NEXT_PUBLIC_DEFAULT_FA_ID` in `.env.local` to use a different financial advisor ID.

## Troubleshooting

### Backend Connection Issues
- Ensure the backend server is running on `http://localhost:8123`
- Check that CORS is enabled in the backend (already configured in `fastapi_server.py`)
- Verify network connectivity

### LangSmith Feedback Not Appearing
- Confirm `LANGSMITH_API_KEY` is correct in `.env.local`
- Check that run IDs are being returned from the backend
- View browser console for error messages

### Sources Not Displaying
- Verify the backend is returning `citations` in the response
- Check that citations follow the expected format
- Look for `x-sources` header in network tab

### Styling Issues
- Run `yarn install` to ensure all dependencies are installed
- Clear `.next` cache: `rm -rf .next`
- Restart the development server

## Development Notes

- The UI uses the Vercel AI SDK for streaming responses
- All components are built with TypeScript for type safety
- Tailwind CSS is used for styling with a professional color palette
- No icons are used per design requirements - all UI elements use text labels

## Support

For issues or questions:
1. Check the backend logs at `src/interactive/api/fastapi_server.py`
2. Review LangSmith traces for detailed request/response data
3. Check browser console for client-side errors

## Future Enhancements

Potential improvements:
- Add conversation history sidebar
- Implement export conversation functionality
- Add advanced filtering for sources
- Support for file uploads
- Multi-language support
- Dark mode toggle
