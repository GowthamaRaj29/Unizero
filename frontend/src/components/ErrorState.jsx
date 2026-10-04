function ErrorState({
  title = "Something went wrong",
  message = "We could not load this information right now.",
  onRetry,
  action,
}) {
  return (
    <div className="flex min-h-[220px] items-center justify-center px-4 py-8">
      <div className="w-full max-w-xl rounded-2xl border border-red-500/30 bg-red-500/5 p-8 text-center shadow-lg shadow-red-900/10">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-red-400/30 bg-red-500/10 text-red-300">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className="h-8 w-8"
            aria-hidden="true"
          >
            <path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
          </svg>
        </div>

        <h3 className="text-2xl font-bold text-white">{title}</h3>

        {message && (
          <p className="mt-3 text-sm leading-6 text-slate-400">
            {message}
          </p>
        )}

        {(onRetry || action) && (
          <div className="mt-6 flex justify-center">
            {action || (
              <button
                type="button"
                className="primary-button"
                onClick={onRetry}
              >
                Try again
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ErrorState;
