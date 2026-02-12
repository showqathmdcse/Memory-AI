# NATS JetStream Streaming Guide

Complete guide for using NATS JetStream for real-time streaming in your Python agent service.

---

## 🎯 Why NATS Instead of Kafka?

NATS JetStream is a **lightweight, high-performance** alternative to Kafka:

### ✅ Advantages Over Kafka

| Feature | NATS | Kafka |
|---------|------|-------|
| **Setup** | Single binary, 1 command | Complex (Zookeeper + Kafka + UI) |
| **Memory** | ~20MB | ~500MB+ |
| **Startup** | < 1 second | ~30 seconds |
| **Config** | Zero config needed | Lots of config |
| **Learning Curve** | Simple | Steep |
| **Docker Image** | 15MB | 500MB+ |
| **Perfect For** | Dev & Small Teams | Enterprise Scale |

### 🚀 NATS is Perfect When:
- ✅ You want real-time streaming **without complexity**
- ✅ You need something **fast to set up**
- ✅ You're building for **small to medium teams**
- ✅ You want **low resource usage**
- ✅ You need **good enough** persistence (not mission-critical)

---

## 🎬 Quick Start

### Option 1: Disabled (Default)

```bash
# In .env
NATS_STREAMING_ENABLED=false

# Start backend (no NATS needed)
python3 -m uvicorn main:app --reload --port 6080
```

### Option 2: Enable Streaming

```bash
# 1. Start NATS (one command!)
docker-compose -f docker-compose.nats.yml up -d

# 2. Enable in .env
NATS_STREAMING_ENABLED=true

# 3. Install NATS client
pip install nats-py

# 4. Start backend
python3 -m uvicorn main:app --reload --port 6080
```

**That's it!** NATS is running. No complex setup, no configuration files.

---

## 📋 Configuration

### Environment Variables (.env)

```bash
# Enable/Disable Streaming
NATS_STREAMING_ENABLED=false  # Set to 'true' to enable

# NATS Connection
NATS_URL=nats://localhost:4222

# Stream Configuration
NATS_STREAM_NAME=AGENT_STREAM
NATS_SUBJECT_MESSAGES=agent.messages
NATS_SUBJECT_CODE_CHANGES=agent.code

# Retention Settings
NATS_MAX_AGE_SECONDS=86400    # 24 hours
NATS_MAX_MSGS=10000            # Max 10k messages
NATS_MAX_BYTES=10485760        # 10MB
```

### How It Works

**When DISABLED (default):**
- Zero overhead
- Works exactly as before
- No NATS connection

**When ENABLED:**
- Connects to NATS on startup
- Streams messages to subjects
- Falls back gracefully if NATS unavailable

---

## 🔧 Backend Integration

The backend **automatically** uses NATS when enabled. No code changes needed!

### What Gets Streamed

```python
# 1. Agent Messages
Subject: agent.messages.{user_id}.{chat_id}
{
  "type": "start|response|error|end",
  "content": {...},
  "timestamp": 1234567890.123
}

# 2. Code Changes (Line-by-Line)
Subject: agent.code.{user_id}.{chat_id}
{
  "type": "line|done",
  "file_path": "User.java",
  "line_number": 0,
  "content": "public class User {",
  "total_lines": 20,
  "current_line": 1
}
```

---

## 💻 VS Code Extension Integration

### Step 1: Install NATS Client

```bash
# In your VS Code extension directory
npm install nats.ws
```

### Step 2: Create NATS Consumer

Create `src/services/nats-consumer.ts`:

```typescript
import { connect, StringCodec, JetStreamClient } from 'nats.ws';
import * as vscode from 'vscode';

export interface NATSMessage {
    type: string;
    user_id: string;
    chat_id: string;
    content: any;
    metadata?: any;
    timestamp?: number;
}

export class NATSConsumer {
    private nc: any;
    private js: JetStreamClient | null = null;
    private sc = StringCodec();
    private userId: string;
    private chatId: string;

    constructor(
        natsUrl: string,
        userId: string,
        chatId: string
    ) {
        this.userId = userId;
        this.chatId = chat Id;
    }

    /**
     * Connect to NATS
     */
    async connect(): Promise<void> {
        try {
            // Connect to NATS server
            this.nc = await connect({ 
                servers: 'ws://localhost:4222'  // WebSocket connection
            });
            
            this.js = this.nc.jetstream();
            
            console.log('Connected to NATS JetStream');
            
        } catch (error) {
            console.error('Failed to connect to NATS:', error);
            throw error;
        }
    }

    /**
     * Subscribe to agent messages
     */
    async subscribeToMessages(
        callback: (msg: NATSMessage) => void
    ): Promise<void> {
        if (!this.js) {
            throw new Error('Not connected to NATS');
        }

        try {
            const subject = `agent.messages.${this.userId}.${this.chatId}`;
            
            const consumer = await this.js.consumers.get('AGENT_STREAM');
            const messages = await consumer.consume();
            
            for await (const msg of messages) {
                const data = JSON.parse(this.sc.decode(msg.data));
                callback(data);
                msg.ack();
            }
            
        } catch (error) {
            console.error('Error subscribing to messages:', error);
        }
    }

    /**
     * Subscribe to code changes
     */
    async subscribeToCodeChanges(
        callback: (msg: NATSMessage) => void
    ): Promise<void> {
        if (!this.js) {
            throw new Error('Not connected to NATS');
        }

        try {
            const subject = `agent.code.${this.userId}.${this.chatId}`;
            
            const consumer = await this.js.consumers.get('AGENT_STREAM');
            const messages = await consumer.consume();
            
            for await (const msg of messages) {
                const data = JSON.parse(this.sc.decode(msg.data));
                callback(data);
                msg.ack();
            }
            
        } catch (error) {
            console.error('Error subscribing to code changes:', error);
        }
    }

    /**
     * Disconnect from NATS
     */
    async disconnect(): Promise<void> {
        if (this.nc) {
            await this.nc.drain();
            await this.nc.close();
            console.log('Disconnected from NATS');
        }
    }
}
```

### Step 3: Real-Time UI Manager

Create `src/services/realtime-ui.ts`:

```typescript
import * as vscode from 'vscode';
import { NATSConsumer, NATSMessage } from './nats-consumer';

export class RealTimeUI {
    private consumer: NATSConsumer;
    private statusBar: vscode.StatusBarItem;
    private outputChannel: vscode.OutputChannel;

    constructor(
        natsUrl: string,
        userId: string,
        chatId: string,
        outputChannel: vscode.OutputChannel
    ) {
        this.consumer = new NATSConsumer(natsUrl, userId, chatId);
        this.outputChannel = outputChannel;
        
        // Create status bar
        this.statusBar = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBar.show();
    }

    /**
     * Initialize and start streaming
     */
    async initialize(): Promise<void> {
        try {
            await this.consumer.connect();
            
            // Subscribe to agent messages
            this.consumer.subscribeToMessages((msg) => {
                this.handleAgentMessage(msg);
            });
            
            // Subscribe to code changes
            this.consumer.subscribeToCodeChanges((msg) => {
                this.handleCodeChange(msg);
            });
            
            this.updateStatus('✅ Connected', 'Streaming enabled');
            vscode.window.showInformationMessage('Real-time streaming enabled!');
            
        } catch (error) {
            this.updateStatus('❌ Offline', 'Not connected');
            vscode.window.showWarningMessage(
                'Could not connect to streaming. Working offline.'
            );
        }
    }

    /**
     * Handle agent message
     */
    private handleAgentMessage(msg: NATSMessage): void {
        switch (msg.type) {
            case 'start':
                this.updateStatus('🔄 Processing...', 'Agent working');
                this.outputChannel.appendLine(`\n🔄 Started: ${msg.content.query}`);
                break;

            case 'response':
                this.outputChannel.appendLine(`✅ Response received`);
                break;

            case 'error':
                this.updateStatus('❌ Error', 'An error occurred');
                vscode.window.showErrorMessage(`Error: ${msg.content.error}`);
                break;

            case 'end':
                this.updateStatus('✅ Complete', 'Task done');
                this.outputChannel.appendLine('✅ Task completed\n');
                break;
        }
    }

    /**
     * Handle code change (line-by-line animation)
     */
    private async handleCodeChange(msg: NATSMessage): Promise<void> {
        if (msg.type === 'line') {
            // Write line to editor
            await this.writeLineToEditor(
                msg.content.file_path,
                msg.content.line_number,
                msg.content.content
            );
            
            // Update progress
            const progress = Math.round(
                (msg.content.current_line / msg.content.total_lines) * 100
            );
            this.updateStatus(
                `✏️ Writing ${progress}%`,
                `Line ${msg.content.current_line} of ${msg.content.total_lines}`
            );
            
        } else if (msg.type === 'done') {
            this.updateStatus('✅ Complete', 'File updated');
            vscode.window.showInformationMessage(
                `✅ Finished editing ${msg.content.file_path}`
            );
        }
    }

    /**
     * Write line to editor
     */
    private async writeLineToEditor(
        filePath: string,
        lineNumber: number,
        content: string
    ): Promise<void> {
        try {
            const document = await vscode.workspace.openTextDocument(filePath);
            const editor = await vscode.window.showTextDocument(document);

            await editor.edit(editBuilder => {
                const position = new vscode.Position(lineNumber, 0);
                editBuilder.insert(position, content + '\n');
            });

            // Scroll to line
            const position = new vscode.Position(lineNumber, 0);
            editor.revealRange(
                new vscode.Range(position, position),
                vscode.TextEditorRevealType.InCenter
            );

            // Animation delay
            await new Promise(resolve => setTimeout(resolve, 50));
            
        } catch (error) {
            console.error('Error writing line:', error);
        }
    }

    /**
     * Update status bar
     */
    private updateStatus(text: string, tooltip: string): void {
        this.statusBar.text = text;
        this.statusBar.tooltip = tooltip;
    }

    /**
     * Dispose resources
     */
    async dispose(): Promise<void> {
        await this.consumer.disconnect();
        this.statusBar.dispose();
    }
}
```

### Step 4: Integrate in Extension

Update `extension.ts`:

```typescript
import * as vscode from 'vscode';
import { RealTimeUI } from './services/realtime-ui';

let realTimeUI: RealTimeUI | null = null;

export function activate(context: vscode.ExtensionContext) {
    console.log('Extension activated');

    const outputChannel = vscode.window.createOutputChannel('Agen Agent');

    // Get settings
    const config = vscode.workspace.getConfiguration('agen');
    const streamingEnabled = config.get<boolean>('streamingEnabled', false);
    
    if (streamingEnabled) {
        realTimeUI = new RealTimeUI(
            'ws://localhost:4222',
            'user123',
            'chat456',
            outputChannel
        );
        
        realTimeUI.initialize();
    }

    // Register commands
    let disposable = vscode.commands.registerCommand('agen.sendMessage', async () => {
        const message = await vscode.window.showInputBox({
            prompt: 'Enter your message'
        });
        
        if (message) {
            // Send to backend
            await fetch('http://localhost:6080/vscode/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: message,
                    user_id: 'user123',
                    chat_id: 'chat456'
                })
            });
        }
    });

    context.subscriptions.push(disposable);
    
    // Clean up
    context.subscriptions.push({
        dispose: () => {
            if (realTimeUI) {
                realTimeUI.dispose();
            }
        }
    });
}
```

### Step 5: Update package.json

```json
{
  "dependencies": {
    "nats.ws": "^1.20.0"
  },
  "contributes": {
    "configuration": {
      "properties": {
        "agen.streamingEnabled": {
          "type": "boolean",
          "default": false,
          "description": "Enable real-time streaming via NATS"
        }
      }
    }
  }
}
```

---

## 🎬 Complete Usage Example

### 1. Start NATS

```bash
# Start NATS server
docker-compose -f docker-compose.nats.yml up -d

# Check it's running
docker ps | grep nats

# View NATS monitoring
open http://localhost:8222
```

### 2. Enable in Backend

```bash
# In .env
NATS_STREAMING_ENABLED=true

# Start backend
python3 -m uvicorn main:app --reload --port 6080

# Logs show:
# INFO: NATS streaming: ENABLED
# INFO: NATS producer initialized successfully
```

### 3. Enable in VS Code

```json
// In VS Code settings.json
{
  "agen.streamingEnabled": true
}
```

### 4. Test It!

```typescript
// User types: "Create Calculator class"

// Backend streams to NATS:
// 1. Start message
// 2. Tool execution (write_to_file)
// 3. Line-by-line code
// 4. Completion

// VS Code receives:
// → Status bar updates in real-time
// → Code appears line-by-line in editor
// → Progress shown as percentage
// → Notification on completion
```

---

## 🐛 Troubleshooting

### NATS Not Starting

```bash
# Check NATS is running
docker ps | grep nats

# Should show:
# nats-server   "nats-server -js -m 8222"   Up

# View logs
docker logs nats-server

# Restart if needed
docker-compose -f docker-compose.nats.yml restart
```

### Backend Can't Connect

```bash
# Check backend logs
tail -f server.log | grep -i nats

# Should see:
# INFO: NATS streaming: ENABLED
# INFO: NATS producer initialized successfully

# If error:
# WARNING: Failed to initialize NATS producer
# Check NATS is running on port 4222
```

### VS Code Extension Not Receiving

```bash
# Check extension console (Ctrl+Shift+I)
# Should see:
# Connected to NATS JetStream

# Test NATS directly
docker exec -it nats-server nats pub agent.messages.test.test "hello"

# Check monitoring
open http://localhost:8222
```

---

## 📊 Performance Comparison

### NATS JetStream

- **Setup Time:** < 1 minute
- **Memory:** ~20MB
- **Latency:** 2-5ms
- **Messages/sec:** 1M+
- **Storage:** Optional
- **Perfect for:** Dev & small teams

### Kafka

- **Setup Time:** 10-30 minutes
- **Memory:** ~500MB+
- **Latency:** 5-10ms
- **Messages/sec:** 1M+
- **Storage:** Required
- **Perfect for:** Enterprise scale

---

## 🎯 Summary

**Your backend now has NATS JetStream streaming!**

```bash
# Disabled (Default) - Simple
NATS_STREAMING_ENABLED=false

# Enabled - Real-time updates
NATS_STREAMING_ENABLED=true
```

**Key Benefits:**
- ✅ **Lightweight** - Only 20MB vs 500MB+ for Kafka
- ✅ **Fast Setup** - 1 command vs complex Kafka setup
- ✅ **Simple** - Zero config needed
- ✅ **Powerful** - 1M+ messages/sec
- ✅ **Perfect for Dev** - Great for small to medium teams

**Files Created:**
- `nats_config.py` - Configuration
- `nats_producer.py` - Producer
- `nats_streaming_service.py` - Service wrapper
- `docker-compose.nats.yml` - Docker setup
- Updated `.env` with NATS settings

**Next Steps:**
1. Start NATS: `docker-compose -f docker-compose.nats.yml up -d`
2. Enable: `NATS_STREAMING_ENABLED=true`
3. Install client: `npm install nats.ws`
4. Copy TypeScript code above
5. Test with a message!

Your backend is now streaming with NATS JetStream! 🚀
