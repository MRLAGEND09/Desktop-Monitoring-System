const STYLES = {
  online:    'bg-green-500/20 text-green-400 border-green-700',
  offline:   'bg-gray-700/40 text-gray-400 border-gray-700',
  idle:      'bg-yellow-500/20 text-yellow-400 border-yellow-700',
  streaming: 'bg-blue-500/20 text-blue-400 border-blue-700',
};

export default function StatusBadge({ status = 'offline' }) {
  return (
    <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${STYLES[status] ?? STYLES.offline}`}>
      {status}
    </span>
  );
}
