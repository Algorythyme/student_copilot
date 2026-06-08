type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const isDev = import.meta.env.DEV;

function shouldLog(level: LogLevel): boolean {
  return isDev || level === 'warn' || level === 'error';
}

function write(level: LogLevel, scope: string, message: string, context?: Record<string, unknown>) {
  if (!shouldLog(level)) return;

  const payload = context ? [{ scope, ...context }] : [{ scope }];
  const prefix = `[${level.toUpperCase()}] ${message}`;

  if (level === 'error') {
    console.error(prefix, ...payload);
    return;
  }

  if (level === 'warn') {
    console.warn(prefix, ...payload);
    return;
  }

  if (level === 'info') {
    console.info(prefix, ...payload);
    return;
  }

  console.debug(prefix, ...payload);
}

export const logger = {
  context(scope: string) {
    return {
      debug: (message: string, context?: Record<string, unknown>) => write('debug', scope, message, context),
      info: (message: string, context?: Record<string, unknown>) => write('info', scope, message, context),
      warn: (message: string, context?: Record<string, unknown>) => write('warn', scope, message, context),
      error: (message: string, context?: Record<string, unknown>) => write('error', scope, message, context),
    };
  },
};
