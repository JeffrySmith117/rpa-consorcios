export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <div className="progresso" role="status">
      <span className="spinner" /> {texto}
    </div>
  );
}