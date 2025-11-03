# Next.js Integration Guide

Learn how to integrate vLLM Batch Server with your Next.js application.

---

## 🎯 Overview

This guide shows you how to:
- Submit batch jobs from Next.js API routes
- Upload files from the frontend
- Display batch status in real-time
- Receive webhook notifications

---

## 🚀 Quick Start

### **1. Install Dependencies**

```bash
npm install axios
# or
pnpm add axios
```

### **2. Create API Route**

```typescript
// app/api/batch/submit/route.ts
import { NextRequest, NextResponse } from 'next/server';

const BATCH_API_URL = process.env.BATCH_API_URL || 'http://localhost:4080';

export async function POST(request: NextRequest) {
  try {
    const { input_file_id, model } = await request.json();
    
    const response = await fetch(`${BATCH_API_URL}/v1/batches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input_file_id,
        metadata: { model: model || 'google/gemma-3-4b-it' }
      }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to submit batch');
    }
    
    const data = await response.json();
    
    return NextResponse.json({
      batch_id: data.id,
      status: data.status,
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to submit batch' },
      { status: 500 }
    );
  }
}
```

### **3. Create Frontend Component**

```typescript
// app/components/BatchSubmit.tsx
'use client';

import { useState } from 'react';

export default function BatchSubmit() {
  const [fileId, setFileId] = useState('');
  const [batchId, setBatchId] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch('/api/batch/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input_file_id: fileId,
          model: 'google/gemma-3-4b-it',
        }),
      });

      const data = await response.json();
      setBatchId(data.batch_id);
    } catch (error) {
      console.error('Error submitting batch:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h2 className="text-2xl font-bold mb-4">Submit Batch Job</h2>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Input File ID
          </label>
          <input
            type="text"
            value={fileId}
            onChange={(e) => setFileId(e.target.value)}
            className="w-full px-3 py-2 border rounded"
            placeholder="file-abc123"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? 'Submitting...' : 'Submit Batch'}
        </button>
      </form>

      {batchId && (
        <div className="mt-4 p-4 bg-green-50 rounded">
          <p className="text-sm text-green-800">
            Batch submitted! ID: <code>{batchId}</code>
          </p>
        </div>
      )}
    </div>
  );
}
```

### **4. Use in Page**

```typescript
// app/page.tsx
import BatchSubmit from './components/BatchSubmit';

export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold text-center mb-8">
        vLLM Batch Server
      </h1>
      <BatchSubmit />
    </main>
  );
}
```

---

## 📚 Advanced Examples

### **Example 1: File Upload**

```typescript
// app/api/batch/upload/route.ts
import { NextRequest, NextResponse } from 'next/server';

const BATCH_API_URL = process.env.BATCH_API_URL || 'http://localhost:4080';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      return NextResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      );
    }

    // Upload to vLLM Batch Server
    const uploadFormData = new FormData();
    uploadFormData.append('file', file);
    uploadFormData.append('purpose', 'batch');

    const uploadResponse = await fetch(`${BATCH_API_URL}/v1/files`, {
      method: 'POST',
      body: uploadFormData,
    });

    if (!uploadResponse.ok) {
      throw new Error('Failed to upload file');
    }

    const uploadData = await uploadResponse.json();
    const fileId = uploadData.id;

    // Submit batch
    const batchResponse = await fetch(`${BATCH_API_URL}/v1/batches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input_file_id: fileId,
        metadata: { model: 'google/gemma-3-4b-it' }
      }),
    });

    const batchData = await batchResponse.json();

    return NextResponse.json({
      file_id: fileId,
      batch_id: batchData.id,
      status: 'submitted',
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to process file' },
      { status: 500 }
    );
  }
}
```

```typescript
// app/components/FileUpload.tsx
'use client';

import { useState } from 'react';

export default function FileUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/batch/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error uploading file:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h2 className="text-2xl font-bold mb-4">Upload & Process</h2>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            JSONL File
          </label>
          <input
            type="file"
            accept=".jsonl"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full"
            required
          />
        </div>

        <button
          type="submit"
          disabled={uploading || !file}
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {uploading ? 'Uploading...' : 'Upload & Submit'}
        </button>
      </form>

      {result && (
        <div className="mt-4 p-4 bg-green-50 rounded">
          <p className="text-sm text-green-800">
            File ID: <code>{result.file_id}</code><br />
            Batch ID: <code>{result.batch_id}</code>
          </p>
        </div>
      )}
    </div>
  );
}
```

### **Example 2: Real-Time Status Updates**

```typescript
// app/components/BatchStatus.tsx
'use client';

import { useState, useEffect } from 'react';

interface BatchStatusProps {
  batchId: string;
}

export default function BatchStatus({ batchId }: BatchStatusProps) {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`/api/batch/${batchId}`);
        const data = await response.json();
        setStatus(data);
        
        // Stop polling if completed
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          setLoading(false);
        }
      } catch (error) {
        console.error('Error fetching status:', error);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 5 seconds
    const interval = setInterval(fetchStatus, 5000);

    return () => clearInterval(interval);
  }, [batchId]);

  if (!status) {
    return <div>Loading...</div>;
  }

  return (
    <div className="p-6 border rounded">
      <h3 className="text-xl font-bold mb-4">Batch Status</h3>
      
      <div className="space-y-2">
        <div>
          <span className="font-medium">ID:</span> {status.id}
        </div>
        <div>
          <span className="font-medium">Status:</span>{' '}
          <span className={`px-2 py-1 rounded text-sm ${
            status.status === 'completed' ? 'bg-green-100 text-green-800' :
            status.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-yellow-100 text-yellow-800'
          }`}>
            {status.status}
          </span>
        </div>
        {status.request_counts && (
          <div>
            <span className="font-medium">Progress:</span>{' '}
            {status.request_counts.completed} / {status.request_counts.total}
          </div>
        )}
        {status.metadata?.model && (
          <div>
            <span className="font-medium">Model:</span> {status.metadata.model}
          </div>
        )}
      </div>

      {loading && (
        <div className="mt-4 text-sm text-gray-500">
          Updating every 5 seconds...
        </div>
      )}
    </div>
  );
}
```

```typescript
// app/api/batch/[id]/route.ts
import { NextRequest, NextResponse } from 'next/server';

const BATCH_API_URL = process.env.BATCH_API_URL || 'http://localhost:4080';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const response = await fetch(
      `${BATCH_API_URL}/v1/batches/${params.id}`
    );
    
    if (!response.ok) {
      throw new Error('Failed to fetch batch status');
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch batch status' },
      { status: 500 }
    );
  }
}
```

### **Example 3: Webhook Receiver**

```typescript
// app/api/webhooks/batch/route.ts
import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET!;

function verifySignature(body: string, signature: string): boolean {
  const expected = crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(body)
    .digest('hex');
  
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}

export async function POST(request: NextRequest) {
  try {
    const signature = request.headers.get('x-webhook-signature');
    const body = await request.text();
    
    if (!signature || !verifySignature(body, signature)) {
      return NextResponse.json(
        { error: 'Invalid signature' },
        { status: 401 }
      );
    }
    
    const data = JSON.parse(body);
    
    // Handle different events
    switch (data.event) {
      case 'batch.completed':
        await handleBatchCompleted(data);
        break;
      case 'batch.failed':
        await handleBatchFailed(data);
        break;
      default:
        console.log('Unknown event:', data.event);
    }
    
    return NextResponse.json({ status: 'received' });
  } catch (error) {
    return NextResponse.json(
      { error: 'Webhook processing failed' },
      { status: 500 }
    );
  }
}

async function handleBatchCompleted(data: any) {
  console.log('Batch completed:', data.batch_id);
  // Send email, update database, etc.
}

async function handleBatchFailed(data: any) {
  console.log('Batch failed:', data.batch_id, data.error);
  // Send alert, log error, etc.
}
```

---

## 🔧 Configuration

### **Environment Variables**

```bash
# .env.local
BATCH_API_URL=http://localhost:4080
WEBHOOK_SECRET=your-secret-key
```

---

## 🎯 Best Practices

### **1. Use Server Components for Data Fetching**
```typescript
// app/batches/page.tsx
async function getBatches() {
  const res = await fetch(`${process.env.BATCH_API_URL}/v1/batches`, {
    cache: 'no-store' // Always fetch fresh data
  });
  return res.json();
}

export default async function BatchesPage() {
  const batches = await getBatches();
  return <BatchList batches={batches} />;
}
```

### **2. Use API Routes for Mutations**
```typescript
// Always use API routes for POST/PUT/DELETE
// Never call external APIs directly from client components
```

### **3. Handle Loading States**
```typescript
'use client';

import { useState } from 'react';

export default function Component() {
  const [loading, setLoading] = useState(false);
  
  // Show loading state to user
  if (loading) return <Spinner />;
}
```

---

## 📖 Full Example Application

See `examples/integrations/nextjs/` for a complete Next.js application with:
- File upload with drag-and-drop
- Real-time batch status updates
- Webhook receiver
- Result visualization
- TypeScript types

---

## 🔗 Related Documentation

- [API Reference](../../reference/api.md)
- [Webhook Events](../../reference/webhooks.md)
- [Getting Started Guide](../getting-started.md)

---

**Need help?** Open an issue or ask in discussions!

