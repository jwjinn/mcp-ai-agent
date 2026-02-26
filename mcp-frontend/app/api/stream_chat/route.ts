
export async function POST(req: Request) {
    try {
        const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
        const body = await req.json();

        console.log(`[Proxy] Forwarding request to: ${backendUrl}/api/stream_chat`);

        const response = await fetch(`${backendUrl}/api/stream_chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[Proxy] Backend returned error: ${response.status} ${errorText}`);
            return new Response(`Backend Error: ${errorText}`, { status: response.status });
        }

        // SSE 스트림을 그대로 파이프(Pipe)하여 클라이언트에 전달합니다.
        return new Response(response.body, {
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        });
    } catch (error: any) {
        console.error("[Proxy] Critical Error:", error);
        return new Response(`Proxy Error: ${error.message}`, { status: 500 });
    }
}
