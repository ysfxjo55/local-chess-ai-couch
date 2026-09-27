import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode; title?: string };
type State = { hasError: boolean };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep production diagnostics free of player data while leaving a useful
    // signal for the hosting platform's console/error collector.
    console.error("Chess Coach interface error", error.name, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <section className="mx-auto max-w-lg rounded-xl border border-blunder/30 bg-slate-surface p-6 text-center" role="alert">
        <AlertTriangle className="mx-auto size-6 text-blunder" aria-hidden="true" />
        <h1 className="mt-3 text-lg font-semibold text-ink">{this.props.title ?? "This part of Chess Coach could not load"}</h1>
        <p className="mt-2 text-sm text-ink-muted">Your saved games and learning history are unchanged. Try again, or return to the dashboard.</p>
        <div className="mt-5 flex justify-center gap-2">
          <Button onClick={() => this.setState({ hasError: false })} className="gap-2"><RefreshCw className="size-4" />Try again</Button>
          <Button asChild variant="outline"><Link to="/">Dashboard</Link></Button>
        </div>
      </section>
    );
  }
}
