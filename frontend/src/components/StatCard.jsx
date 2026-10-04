function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendLabel,
  variant = "default",
}) {
  return (
    <div className={`stat-card stat-card-${variant}`}>
      <div className="stat-card-top">
        <div className="stat-card-icon">
          {Icon && <Icon size={19} strokeWidth={1.8} />}
        </div>

        {trend !== undefined && (
          <span
            className={`stat-card-trend ${
              trend >= 0 ? "trend-positive" : "trend-negative"
            }`}
          >
            {trend >= 0 ? "+" : ""}
            {trend}%
          </span>
        )}
      </div>

      <div className="stat-card-value">{value}</div>

      <div className="stat-card-title">{title}</div>

      {(subtitle || trendLabel) && (
        <div className="stat-card-footer">
          {subtitle && <span>{subtitle}</span>}
          {trendLabel && <span>{trendLabel}</span>}
        </div>
      )}
    </div>
  );
}

export default StatCard;