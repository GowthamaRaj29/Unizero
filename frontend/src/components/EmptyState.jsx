function EmptyState({
  icon: Icon,
  title = "No data available",
  description = "There is nothing to show right now.",
  action,
  secondaryAction,
}) {
  return (
    <div className="flex min-h-[280px] items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/80 p-8 text-center shadow-lg shadow-black/20">
        {Icon && (
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
            <Icon size={28} />
          </div>
        )}

        <h3 className="text-2xl font-bold text-white">{title}</h3>

        {description && (
          <p className="mt-3 text-sm leading-6 text-slate-400">
            {description}
          </p>
        )}

        {(action || secondaryAction) && (
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            {action}
            {secondaryAction}
          </div>
        )}
      </div>
    </div>
  );
}

export default EmptyState;
