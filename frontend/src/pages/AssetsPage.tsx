import { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Database, FileText, LoaderCircle, Plus, Search, Trash2, UploadCloud, X } from 'lucide-react';
import { api } from '../api/client';
import { queryKeys, useDataset, useDatasets, useDeleteDataset, useDeleteDocument, useDocument, useDocuments } from '../api/hooks';
import { DataTable } from '../components/DataTable';
import type { TableColumn } from '../components/DataTable';
import { SideDrawer } from '../components/SideDrawer';
import { Button, EmptyState, ErrorState, PageHeader, Skeleton, formatDate, notify } from '../components/ui';
import type { DatasetItem, DocumentItem } from '../types/api';

type AssetKind = 'documents' | 'datasets';
type AssetRow = DocumentItem | DatasetItem;

function isDocument(item: AssetRow): item is DocumentItem {
  return 'title' in item;
}

export function AssetsPage({ kind }: { kind: AssetKind }) {
  const isDocuments = kind === 'documents';
  const documents = useDocuments();
  const datasets = useDatasets();
  const rows = isDocuments ? documents.data ?? [] : datasets.data ?? [];
  const error = isDocuments ? documents.error : datasets.error;
  const isLoading = isDocuments ? documents.isLoading : datasets.isLoading;
  const refetch = isDocuments ? documents.refetch : datasets.refetch;
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string>();
  const [progress, setProgress] = useState<number>();
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string>();
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const deleteDocument = useDeleteDocument();
  const deleteDataset = useDeleteDataset();
  const datasetPreview = useDataset(!isDocuments ? selected : undefined);

  const filtered = rows.filter((row) => {
    const name = 'title' in row ? `${row.title} ${row.filename}` : row.filename;
    return name.toLowerCase().includes(query.toLowerCase());
  });

  const handleUpload = useCallback(async (file?: File) => {
    if (!file) return;
    const validType = isDocuments
      ? /\.(md|txt)$/i.test(file.name) && file.size <= 2 * 1024 * 1024
      : /\.csv$/i.test(file.name) && file.size <= 10 * 1024 * 1024;
    if (!validType) {
      setUploadError(isDocuments ? 'Choose a .txt or .md file up to 2 MB.' : 'Choose a .csv file up to 10 MB.');
      return;
    }
    setUploadError(undefined);
    setProgress(0);
    try {
      if (isDocuments) await api.uploadDocument(file, setProgress);
      else await api.uploadDataset(file, setProgress);
      await queryClient.invalidateQueries({ queryKey: isDocuments ? queryKeys.documents : queryKeys.datasets });
      setProgress(undefined);
      notify(`${isDocuments ? 'Document' : 'Dataset'} uploaded successfully.`);
    } catch (uploadFailure) {
      setProgress(undefined);
      setUploadError(uploadFailure instanceof Error ? uploadFailure.message : 'Upload failed.');
    }
  }, [isDocuments, queryClient]);

  const remove = async (id: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return;
    try {
      if (isDocuments) await deleteDocument.mutateAsync(id);
      else await deleteDataset.mutateAsync(id);
      setSelected(undefined);
      notify(`${isDocuments ? 'Document' : 'Dataset'} deleted.`);
    } catch (failure) { notify(failure instanceof Error ? failure.message : 'Unable to delete item.', 'error'); }
  };

  const documentColumns: TableColumn<AssetRow>[] = [
    { key: 'title', label: 'Document', render: (item) => isDocument(item) ? <div className="asset-name"><span className="asset-icon"><FileText size={17} /></span><span><strong>{item.title}</strong><small>{item.filename}</small></span></div> : null, sortValue: (item) => isDocument(item) ? item.title : item.filename },
    { key: 'type', label: 'Type', render: (item) => isDocument(item) ? item.content_type.split('/').pop()?.toUpperCase() ?? 'TEXT' : 'CSV', sortValue: (item) => isDocument(item) ? item.content_type : 'csv' },
    { key: 'chunks', label: 'Chunks', render: (item) => isDocument(item) ? item.chunk_count ?? '—' : '—', sortValue: (item) => isDocument(item) ? item.chunk_count ?? 0 : 0 },
    { key: 'size', label: 'Size', render: (item) => isDocument(item) ? formatBytes(item.size_bytes) : '—', sortValue: (item) => isDocument(item) ? item.size_bytes : 0 },
    { key: 'created', label: 'Added', render: (item) => formatDate(item.created_at), sortValue: (item) => item.created_at },
    { key: 'actions', label: '', render: (item) => <button className="icon-button asset-delete" onClick={(event) => { event.stopPropagation(); void remove(item.id, item.filename); }} aria-label={`Delete ${item.filename}`}><Trash2 size={15} /></button> },
  ];
  const datasetColumns: TableColumn<AssetRow>[] = [
    { key: 'filename', label: 'Dataset', render: (item) => !isDocument(item) ? <div className="asset-name"><span className="asset-icon"><Database size={17} /></span><span><strong>{item.filename}</strong><small>{item.columns.length} columns</small></span></div> : null, sortValue: (item) => item.filename },
    { key: 'rows', label: 'Rows', render: (item) => !isDocument(item) ? item.row_count.toLocaleString() : '—', sortValue: (item) => !isDocument(item) ? item.row_count : 0 },
    { key: 'columns', label: 'Columns', render: (item) => !isDocument(item) ? item.columns.map((column) => column.name).slice(0, 3).join(', ') + (item.columns.length > 3 ? ` +${item.columns.length - 3}` : '') : '—' },
    { key: 'created', label: 'Added', render: (item) => formatDate(item.created_at), sortValue: (item) => item.created_at },
    { key: 'actions', label: '', render: (item) => <button className="icon-button asset-delete" onClick={(event) => { event.stopPropagation(); void remove(item.id, item.filename); }} aria-label={`Delete ${item.filename}`}><Trash2 size={15} /></button> },
  ];

  return (
    <div className="page-stack">
      <PageHeader title={isDocuments ? 'Documents' : 'Datasets'} description={isDocuments ? 'Manage indexed text sources used by local document search.' : 'Manage registered CSV files available to controlled tools.'} actions={<Button disabled={progress !== undefined} onClick={() => inputRef.current?.click()}><Plus size={15} /> Upload {isDocuments ? 'document' : 'dataset'}</Button>} />
      <input ref={inputRef} type="file" hidden accept={isDocuments ? '.md,.txt,text/markdown,text/plain' : '.csv,text/csv'} onChange={(event) => { void handleUpload(event.target.files?.[0]); event.target.value = ''; }} />
      <section className={`upload-dropzone ${isDragging ? 'dropzone-active' : ''}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={(event) => { event.preventDefault(); setIsDragging(false); void handleUpload(event.dataTransfer.files[0]); }}>
        {progress !== undefined ? <><LoaderCircle className="spin" size={23} /><strong>Uploading… {progress}%</strong><div className="upload-progress"><span style={{ width: `${progress}%` }} /></div></> : <><UploadCloud size={23} /><strong>Drop {isDocuments ? 'documents' : 'a CSV file'} here</strong><span>or <button onClick={() => inputRef.current?.click()}>browse files</button> · {isDocuments ? 'MD or TXT, up to 2 MB' : 'CSV, up to 10 MB'}</span></>}
      </section>
      {uploadError && <div className="upload-error" role="alert"><X size={15} />{uploadError}<button onClick={() => setUploadError(undefined)} aria-label="Dismiss upload error"><X size={14} /></button></div>}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      <div className="asset-list-heading"><div><strong>{filtered.length} {isDocuments ? 'documents' : 'datasets'}</strong><span> in your workspace</span></div><label className="search-field asset-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${isDocuments ? 'documents' : 'datasets'}…`} aria-label={`Search ${kind}`} /></label></div>
      {isLoading ? <div className="card table-loading"><Skeleton lines={5} /></div> : (
        <div className="card asset-table-card">
          <DataTable<AssetRow>
            rows={filtered}
            rowKey={(item) => item.id}
            onRowClick={(item) => setSelected(item.id)}
            columns={isDocuments ? documentColumns : datasetColumns}
            emptyTitle={query ? 'No matching files' : `No ${kind} uploaded`}
            emptyDescription={query ? 'Try a different name or clear the search.' : isDocuments ? 'Upload policies, reports, and other text documents to make them searchable.' : 'Upload CSV data to register it for controlled analysis.'}
          />
        </div>
      )}
      {selected && isDocuments && <DocumentDrawer documentId={selected} onClose={() => setSelected(undefined)} />}
      {selected && !isDocuments && <SideDrawer title="Dataset preview" onClose={() => setSelected(undefined)}>
        {datasetPreview.isLoading ? <Skeleton lines={5} /> : datasetPreview.isError ? <ErrorState error={datasetPreview.error} retry={() => void datasetPreview.refetch()} /> : datasetPreview.data && <div className="preview-content"><h3>{datasetPreview.data.filename}</h3><p>{datasetPreview.data.row_count.toLocaleString()} rows · {datasetPreview.data.columns.length} columns</p><h4>Schema</h4><div className="schema-list">{datasetPreview.data.columns.map((column) => <div key={column.name}><code>{column.name}</code><span>{column.dtype}</span></div>)}</div><h4>Preview rows</h4><div className="preview-table-wrap"><table><thead><tr>{datasetPreview.data.columns.map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead><tbody>{datasetPreview.data.rows.slice(0, 20).map((row, index) => <tr key={index}>{datasetPreview.data?.columns.map((column) => <td key={column.name}>{String(row[column.name] ?? '—')}</td>)}</tr>)}</tbody></table></div><Button variant="danger" onClick={() => void remove(datasetPreview.data?.id ?? selected, datasetPreview.data?.filename ?? selected)}><Trash2 size={14} /> Delete dataset</Button></div>}
      </SideDrawer>}
    </div>
  );
}

function DocumentDrawer({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const preview = useDocument(documentId);
  return <SideDrawer title="Document preview" onClose={onClose}>{preview.isLoading ? <Skeleton lines={5} /> : preview.isError ? <ErrorState error={preview.error} retry={() => void preview.refetch()} /> : preview.data ? <div className="preview-content"><h3>{preview.data.title}</h3><p>{preview.data.filename} · {preview.data.chunks.length} chunks</p><div className="document-chunks">{preview.data.chunks.map((chunk) => <article key={chunk.id}><span>Chunk {chunk.chunk_index + 1}</span><p>{chunk.content}</p></article>)}</div></div> : <EmptyState title="No preview available" description="The document is registered but preview content could not be loaded." />}</SideDrawer>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
