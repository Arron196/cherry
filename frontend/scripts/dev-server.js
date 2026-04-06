/* eslint-disable @typescript-eslint/no-require-imports */
const net = require('net');
const { spawn } = require('child_process');

/* 
  Custom Development Server Script (Random Port Mode)
  Purpose: Finds a RANDOM available ephemeral port (by listening on port 0) 
  and starts Next.js on that port to avoid EACCES/EADDRINUSE errors.
*/

function getRandomAvailablePort() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.unref(); // Don't let this server keep the process alive
        server.on('error', reject);

        // Listen on port 0 to let the OS assign a random available port
        server.listen(0, () => {
            const { port } = server.address();
            server.close(() => {
                resolve(port);
            });
        });
    });
}

function startServer(port) {
    console.log(`\x1b[36m[Custom Dev Server] Starting Next.js on create random port: ${port}...\x1b[0m`);

    const isWindows = process.platform === 'win32';
    const command = isWindows ? 'npx.cmd' : 'npx';

    // Pass the detected random port to Next.js
    const args = ['next', 'dev', '-p', port.toString()];

    // Spawn the Next.js dev server
    const child = spawn(command, args, {
        stdio: 'inherit',
        shell: true,
    });

    child.on('error', (err) => {
        console.error(`\x1b[31m[Custom Dev Server] Failed to start server: ${err.message}\x1b[0m`);
        process.exit(1);
    });

    child.on('exit', (code, signal) => {
        if (signal) {
            console.log(`\x1b[33m[Custom Dev Server] Process killed with signal ${signal}\x1b[0m`);
        }
        process.exit(code || 0);
    });
}

(async () => {
    try {
        const port = await getRandomAvailablePort();
        startServer(port);
    } catch (err) {
        console.error(`\x1b[31m[Custom Dev Server] Failed to get random port: ${err.message}\x1b[0m`);
        process.exit(1);
    }
})();
