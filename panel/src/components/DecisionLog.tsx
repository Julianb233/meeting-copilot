interface Decision {
  id: string
  text: string
  timestamp: string
}

export function DecisionLog({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return <p className="text-sm text-zinc-500">No decisions recorded</p>
  }

  return (
    <div className="space-y-2">
      {decisions.map((decision) => (
        <div key={decision.id}>
          <span className="text-xs text-zinc-600">{decision.timestamp}</span>
          <p className="text-sm text-zinc-300">{decision.text}</p>
        </div>
      ))}
    </div>
  )
}
