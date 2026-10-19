import React from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ErrorState } from '@/components/ErrorState';
import { recordError } from '@/lib/crashLog';
import { colors, spacing } from '@/lib/theme';

/**
 * The app root's last line of defence. Before 2026-10-19 there was no error
 * boundary anywhere, so one screen throwing while it rendered closed the whole
 * app and left no trace. Now the error is logged to `app_errors` (kind
 * `render`, with React's component stack) and the member sees a plain
 * "Something went wrong" with Retry, which remounts the app below this point.
 *
 * A class component because React only offers error boundaries as classes.
 */

interface Props {
  children: React.ReactNode;
  /** Called on Retry, before the tree remounts. App resets its navReady here
   *  so a notification tapped while the fallback was up replays on onReady. */
  onReset?: () => void;
}

interface State {
  // A flag, not the error: `throw 0` would otherwise read as "no error" and
  // re-render the children that just threw.
  hasError: boolean;
  attempt: number;
}

// "Logged" is true the moment this renders: the report is in storage before
// any send is tried. "Sent" would not be, offline (crashLog.ts).
const COPY = {
  title: 'Something went wrong',
  cause: 'The app hit an error. We’ve logged it so we can fix it. Retry to reload.',
  kind: 'server' as const,
};
const REPEAT = 'If this keeps happening, close Signalbase and open it again.';
// From the second Retry the cause gains the next step. In the cause, not the
// `reassurance` prop, which verify_error_states.ts keeps to Picks home.
const REPEAT_COPY = { ...COPY, cause: `${COPY.cause} ${REPEAT}` };

export class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, attempt: 0 };

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo): void {
    void recordError('render', error, info.componentStack ?? null);
  }

  private retry = (): void => {
    this.props.onReset?.();
    this.setState((s) => ({ hasError: false, attempt: s.attempt + 1 }));
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      return (
        <SafeAreaView style={styles.screen}>
          {/* Scrolls so Retry stays reachable at the largest text sizes. */}
          <ScrollView contentContainerStyle={styles.content}>
            {/* error={null}: ErrorState renders NOTHING for an abort-shaped
                error, which is right for a load and wrong for a crash. The
                copy prop supplies every word shown. */}
            <ErrorState
              what="the app"
              error={null}
              copy={this.state.attempt > 0 ? REPEAT_COPY : COPY}
              onRetry={this.retry}
            />
          </ScrollView>
        </SafeAreaView>
      );
    }
    // The key remounts everything below on Retry, so a screen that threw
    // starts from scratch rather than from the state that broke it.
    return <React.Fragment key={this.state.attempt}>{this.props.children}</React.Fragment>;
  }
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: spacing.lg },
});
