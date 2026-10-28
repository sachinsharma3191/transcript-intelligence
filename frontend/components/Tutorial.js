"use client";

// A collapsed box at the top of each step: what it does, and one thing to try.
export default function Tutorial({ what, tryIt }) {
  return (
    <details className="tutorial">
      <summary>How this step works</summary>
      <p>{what}</p>
      <p><b>Try:</b> {tryIt}</p>
    </details>
  );
}
