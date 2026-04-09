import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://localhost:18941";

const HOP_BY_HOP_HEADERS = new Set([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
]);

type ProxyContext = {
    params: Promise<{
        path: string[];
    }>;
};

export async function proxyBackendRequest(
    request: NextRequest,
    context: ProxyContext,
    prefix = "",
) {
    const { path } = await context.params;
    const targetPath = [prefix, ...path].filter(Boolean).join("/");
    const target = new URL(targetPath, `${INTERNAL_API_URL.replace(/\/+$/, "")}/`);
    target.search = request.nextUrl.search;

    const headers = new Headers(request.headers);
    for (const header of HOP_BY_HOP_HEADERS) {
        headers.delete(header);
    }

    const response = await fetch(target, {
        method: request.method,
        headers,
        body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
        redirect: "manual",
    });

    const responseHeaders = new Headers(response.headers);
    for (const header of HOP_BY_HOP_HEADERS) {
        responseHeaders.delete(header);
    }

    return new NextResponse(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
    });
}

export const proxyApiBackendRequest = (request: NextRequest, context: ProxyContext) =>
    proxyBackendRequest(request, context);

export const proxyV1BackendRequest = (request: NextRequest, context: ProxyContext) =>
    proxyBackendRequest(request, context, "v1");
