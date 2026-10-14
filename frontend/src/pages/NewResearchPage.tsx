import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, ChevronDown, FileText, Lightbulb, Plus, Sparkles, Table2 } from 'lucide-react';
import { useCreateRun, useDatasets, useDocuments } from '../api/hooks';
import { Button, Card, ErrorState, PageHeader, Skeleton, notify } from '../components/ui';

export const taskTemplates = [
  'Analyze Q3 sales by region, compare against targets, and recommend actions.',
  'Summarize customer satisfaction trends by region and highlight key risks.',
  'Compare supplier delivery performance and defect rates against policy thresholds.',
  'Review the returns policy and customer feedback for recurring service issues.',
  'Analyze product category profitability and identify pricing opportunities.',
  'Compare regional expansion goals with recent sales performance.',
];

export function validateResearchTask(task: string): string | undefined {
  const trimmed = task.trim();
  if (trimmed.length < 10) return 'Enter at least 10 characters describing the research task.';
  if (trimmed.length > 4000) return 'Keep the task to 4,000 characters or fewer.';
  return undefined;
}

export function NewResearchPage() {
  const navigate = useNavigate();
  const [task, setTask] = useState('');
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [advanced, setAdvanced] = useState(false);
  const [maxRetries, setMaxRetries] = useState(2);
  const [maxReplans, setMaxReplans] = useState(2);
  const createRun = useCreateRun();
  const datasets = useDatasets();
  const documents = useDocuments();
  const validationError = useMemo(() => validateResearchTask(task), [task]);
  const isValid = !validationError;

  const toggle = (current: string[], id: string, setter: (value: string[]) => void) => {
    setter(current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  };
  const launch = async () => {
    if (!isValid) return;
    try {
      const result = await createRun.mutateAsync({
        task: task.trim(),
        max_retries: maxRetries,
        max_replans: maxReplans,
        dataset_ids: selectedDatasets,
        document_ids: selectedDocuments,
      });
      notify('Research run created. Follow progress live.');
      navigate(`/runs/${result.run_id}`);
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not create the run.', 'error');
    }
  };
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void launch();
  };

  return (
    <div className="page-stack page-narrow">
      <PageHeader title="New research" description="Describe the question. ResearchPilot will plan, gather local evidence, validate, and report." actions={<Button variant="ghost" onClick={() => navigate(-1)}><ArrowLeft size={15} /> Back</Button>} />
      <form onSubmit={(event) => void submit(event)} className="research-form">
        <Card className="form-card">
          <div className="field-heading"><div className="field-icon"><Sparkles size={17} /></div><div><label htmlFor="research-task">What would you like to research?</label><p>Be specific about the data, comparison, and outcome you need.</p></div></div>
          <textarea
            id="research-task"
            value={task}
            onChange={(event) => setTask(event.target.value)}
            maxLength={4000}
            rows={7}
            placeholder="e.g. Analyze Q3 sales by region, compare against targets in the policy documents, and recommend actions."
            aria-invalid={Boolean(task && validationError)}
            aria-describedby="task-help task-counter"
            autoFocus
          />
          <div className="field-footer"><span id="task-help" className={task && validationError ? 'field-error' : 'field-hint'}>{task && validationError ? validationError : '10–4,000 characters'}</span><span id="task-counter" className={task.length > 3800 ? 'counter-warning' : ''}>{task.length.toLocaleString()} / 4,000</span></div>
          <div className="templates-block">
            <div className="templates-title"><Lightbulb size={15} /> Start with an example</div>
            <div className="template-grid">{taskTemplates.map((template) => <button key={template} type="button" className="template-button" onClick={() => setTask(template)}><span>{template}</span><Plus size={14} /></button>)}</div>
          </div>
        </Card>

        <Card title="Research scope" className="form-card">
          <p className="form-intro">Optionally narrow the local sources available for this run. Leave both empty to use all indexed sources.</p>
          {(datasets.isError || documents.isError) && <ErrorState error={datasets.error ?? documents.error} retry={() => { void datasets.refetch(); void documents.refetch(); }} />}
          <div className="scope-grid">
            <div className="scope-picker"><div className="scope-title"><Table2 size={16} /> Datasets <span>{selectedDatasets.length} selected</span></div>
              {datasets.isLoading ? <Skeleton lines={2} /> : datasets.data?.length ? datasets.data.map((dataset) => <label className="scope-option" key={dataset.id}><input type="checkbox" checked={selectedDatasets.includes(dataset.id)} onChange={() => toggle(selectedDatasets, dataset.id, setSelectedDatasets)} /><span><strong>{dataset.filename}</strong><small>{dataset.row_count.toLocaleString()} rows · {dataset.columns.length} columns</small></span></label>) : <p className="scope-empty">No datasets available. <Link to="/datasets">Add a dataset</Link></p>}
            </div>
            <div className="scope-picker"><div className="scope-title"><FileText size={16} /> Documents <span>{selectedDocuments.length} selected</span></div>
              {documents.isLoading ? <Skeleton lines={2} /> : documents.data?.length ? documents.data.map((document) => <label className="scope-option" key={document.id}><input type="checkbox" checked={selectedDocuments.includes(document.id)} onChange={() => toggle(selectedDocuments, document.id, setSelectedDocuments)} /><span><strong>{document.title}</strong><small>{document.filename} · {document.chunk_count ?? 0} chunks</small></span></label>) : <p className="scope-empty">No documents available. <Link to="/documents">Add a document</Link></p>}
            </div>
          </div>
        </Card>

        <Card className="form-card advanced-card">
          <button type="button" className="advanced-toggle" aria-expanded={advanced} onClick={() => setAdvanced((value) => !value)}><span><ChevronDown className={advanced ? 'rotate-chevron' : ''} size={16} /><span><strong>Advanced settings</strong><small>Control retry and replan limits</small></span></span><span className="advanced-summary">{maxRetries} retries · {maxReplans} replans</span></button>
          {advanced && <div className="advanced-fields"><label>Maximum tool retries<select value={maxRetries} onChange={(event) => setMaxRetries(Number(event.target.value))}>{[0, 1, 2, 3, 4, 5].map((count) => <option key={count} value={count}>{count}</option>)}</select></label><label>Maximum replans<select value={maxReplans} onChange={(event) => setMaxReplans(Number(event.target.value))}>{[0, 1, 2].map((count) => <option key={count} value={count}>{count}</option>)}</select></label></div>}
        </Card>
        {createRun.isError && <ErrorState error={createRun.error} retry={() => void launch()} />}
        <div className="form-submit-row"><span className="submit-note">Runs use controlled local tools and cite their evidence.</span><Button type="submit" disabled={!isValid || createRun.isPending}>{createRun.isPending ? 'Starting run…' : 'Start research'}<ArrowRight size={16} /></Button></div>
      </form>
    </div>
  );
}
