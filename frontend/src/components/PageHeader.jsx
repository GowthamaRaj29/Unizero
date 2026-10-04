function PageHeader({
  title,
  description,
  action,
  eyebrow,
}) {
  return (
    <div className="page-header">
      <div className="page-header-content">
        {eyebrow && (
          <div className="page-header-eyebrow">
            {eyebrow}
          </div>
        )}

        <h1>{title}</h1>

        {description && (
          <p>{description}</p>
        )}
      </div>

      {action && (
        <div className="page-header-action">
          {action}
        </div>
      )}
    </div>
  );
}

export default PageHeader;