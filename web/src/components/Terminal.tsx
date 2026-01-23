import { useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';

interface TerminalProps {
  sessionId: number;
  token: string;
  onDisconnect?: () => void;
  onError?: (error: string) => void;
}

export interface TerminalHandle {
  disconnect: () => void;
}

export const Terminal = forwardRef<TerminalHandle, TerminalProps>(function Terminal(
  { sessionId, token, onDisconnect, onError },
  ref
) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  const connect = useCallback(() => {
    if (!terminalRef.current || xtermRef.current) return;

    // Create terminal with Nethack-friendly settings
    const terminal = new XTerm({
      cursorBlink: true,
      fontFamily: '"Fira Code", "DejaVu Sans Mono", "Menlo", monospace',
      fontSize: 14,
      lineHeight: 1.1,
      theme: {
        background: '#0d0d0d',
        foreground: '#c0c0c0',
        cursor: '#f7931a',
        cursorAccent: '#0d0d0d',
        selectionBackground: 'rgba(247, 147, 26, 0.3)',
        // Nethack color palette
        black: '#0d0d0d',
        red: '#ff5555',
        green: '#50fa7b',
        yellow: '#f1fa8c',
        blue: '#6272a4',
        magenta: '#ff79c6',
        cyan: '#8be9fd',
        white: '#c0c0c0',
        brightBlack: '#4d4d4d',
        brightRed: '#ff6e67',
        brightGreen: '#5af78e',
        brightYellow: '#f4f99d',
        brightBlue: '#caa9fa',
        brightMagenta: '#ff92d0',
        brightCyan: '#9aedfe',
        brightWhite: '#ffffff',
      },
    });

    // Add addons
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(new WebLinksAddon());

    // Open terminal in container
    terminal.open(terminalRef.current);

    // Fit to container
    setTimeout(() => {
      fitAddon.fit();
    }, 0);

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Connect to WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/terminal/${sessionId}?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      terminal.writeln('\x1b[33mConnecting to Orange Nethack...\x1b[0m');
      // Send initial terminal size
      const { cols, rows } = terminal;
      ws.send(JSON.stringify({ type: 'resize', cols, rows }));
    };

    ws.onmessage = (event) => {
      terminal.write(event.data);
    };

    ws.onerror = () => {
      terminal.writeln('\x1b[31mConnection error\x1b[0m');
      onError?.('WebSocket connection error');
    };

    ws.onclose = (event) => {
      if (event.code !== 1000) {
        terminal.writeln(`\x1b[31mConnection closed (code: ${event.code})\x1b[0m`);
      }
      onDisconnect?.();
    };

    // Handle terminal input
    terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Handle resize
    const handleResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        const { cols, rows } = terminal;
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup function
    return () => {
      window.removeEventListener('resize', handleResize);
      ws.close();
      terminal.dispose();
      xtermRef.current = null;
      wsRef.current = null;
      fitAddonRef.current = null;
    };
  }, [sessionId, token, onDisconnect, onError]);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup?.();
    };
  }, [connect]);

  // Expose disconnect method to parent
  useImperativeHandle(ref, () => ({
    disconnect: () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (xtermRef.current) {
        xtermRef.current.dispose();
      }
    },
  }), []);

  // Focus terminal when clicking on container
  const handleClick = () => {
    xtermRef.current?.focus();
  };

  return (
    <div
      ref={terminalRef}
      onClick={handleClick}
      className="w-full h-full bg-[#0d0d0d]"
      style={{ padding: '8px' }}
    />
  );
});
