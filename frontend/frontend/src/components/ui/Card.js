export default function Card({
  title,
  subtitle,
  icon,
  right,
  children,
  bodyClassName = "px-5 py-4",
}) {
  return (
    <div className="rounded-2xl border bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            {icon ? <span className="text-gray-700">{icon}</span> : null}
            <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          </div>
          {subtitle ? (
            <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        {right}
      </div>
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}
