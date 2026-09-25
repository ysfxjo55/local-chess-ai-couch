import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <p className="text-4xl">🔍</p>
      <h1 className="text-lg font-semibold text-ink">Page not found</h1>
      <Link to="/" className="text-sm text-amber hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
