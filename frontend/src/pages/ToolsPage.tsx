import { useState } from 'react';
import { Calculator, ChevronDown, FileSearch, FileText, Table2, Wrench } from 'lucide-react';
import { useTools } from '../api/hooks';
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui';

const toolIcons: Record<string, typeof Wrench> = {
  document_search: FileSearch,
  csv_reader: Table2,
  calculator: Calculator,
  report_generator: FileText,
};

export function ToolsPage() {
  const tools = useTools();
  return <div className="page-stack">
    <PageHeader title="Local tools" description="The agent can only access data through these controlled, auditable tools." />
    {tools.isError && <ErrorState error={tools.error} retry={() => void tools.refetch()} />}
    {tools.isLoading ? <div className="tool-grid">{Array.from({ length: 4 }, (_, index) => <Card key={index}><Skeleton lines={4} /></Card>)}</div> : tools.data?.length ? <div className="tool-grid">{tools.data.map((tool) => {
      const Icon = toolIcons[tool.name] ?? Wrench;
      return <ToolCard key={tool.name} tool={tool} Icon={Icon} />;
    })}</div> : <EmptyState title="Tool registry unavailable" description="The API did not return any registered tools." />}
  </div>;
}

function ToolCard({ tool, Icon }: { tool: NonNullable<ReturnType<typeof useTools>['data']>[number]; Icon: typeof Wrench }) {
  const [open, setOpen] = useState(false);
  return <Card className="tool-card"><div className="tool-card-header"><span className="tool-card-icon"><Icon size={20} /></span><span className="tool-availability"><i /> Registered</span></div><h2>{tool.name.replace(/_/g, ' ')}</h2><p>{tool.description}</p><div className="tool-card-meta"><span>Timeout</span><strong>{tool.timeout_seconds ?? '—'}s</strong></div><Button variant="ghost" className="schema-toggle" onClick={() => setOpen((value) => !value)}>{open ? 'Hide schema' : 'View schema'}<ChevronDown className={open ? 'rotate-chevron' : ''} size={15} /></Button>{open && <div className="schema-view"><strong>Input schema</strong><pre>{JSON.stringify(tool.input_schema, null, 2)}</pre>{tool.output_schema && <><strong>Output schema</strong><pre>{JSON.stringify(tool.output_schema, null, 2)}</pre></>}</div>}</Card>;
}
