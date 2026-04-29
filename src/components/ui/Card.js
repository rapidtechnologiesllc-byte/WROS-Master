// Card layout wrapper with optional header actions.
export default function Card({
  title,
  icon,
  right,
  children,
  bodyClassName = "px-5 py-4",
}) {
  return (
    <div className="rounded-2xl border bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-4">
        <div className="flex items-center gap-2">
          {icon ? <span className="text-gray-700">{icon}</span> : null}
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        </div>
        {right}
      </div>
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}