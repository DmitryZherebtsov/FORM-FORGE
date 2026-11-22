export interface KeyValuePair {
  key: string;
  value: string;
  confidence: number;
}

export interface CheckboxItem {
  label: string;
  is_checked: boolean;
  context: string | null;
}

export interface TableData {
  headers: string[];
  rows: string[][];
  title: string | null;
}

export interface ExtractedPage {
  page_number: number;
  headings: string[];
  paragraphs: string[];
  key_values: KeyValuePair[];
  tables: TableData[];
  checkboxes: CheckboxItem[];
  raw_text: string;
}

export interface ExtractedDocument {
  filename: string;
  format: string;
  total_pages: number;
  pages: ExtractedPage[];
  metadata: Record<string, unknown>;
}

export type FieldType =
  | 'text'
  | 'date'
  | 'pesel'
  | 'nip'
  | 'regon'
  | 'postal_code'
  | 'email'
  | 'phone'
  | 'checkbox'
  | 'choice_group'
  | 'table';

export interface FormFieldDTO {
  field_id: string;
  label: string;
  field_type: FieldType;
  value: string;
  is_valid: boolean;
  validation_error: string | null;
  confidence: number;
  needs_review: boolean;
}

export interface ChoiceOptionDTO {
  label: string;
  is_selected: boolean;
}

export interface ChoiceGroupDTO {
  group_id: string;
  label: string | null;
  selection_type: 'single' | 'multiple';
  options: ChoiceOptionDTO[];
  needs_review: boolean;
}

export interface FormSectionDTO {
  section_id: string;
  title: string;
  order: number;
  fields: FormFieldDTO[];
  choice_groups: ChoiceGroupDTO[];
  tables: TableData[];
}

export interface StructuredFormDTO {
  filename: string;
  format: string;
  form_title: string | null;
  sections: FormSectionDTO[];
  total_fields: number;
  fields_needing_review: number;
  overall_confidence: number;
}

export interface FormOptionDTO {
  id: string;
  name: string;
  techName: string;
}

export interface FieldStateDTO {
  type: string;
  query: string;
}

export interface ConsentItemDTO {
  description: string;
  required: boolean;
}

export interface ConsentSectionConfigDTO {
  consents: ConsentItemDTO[];
  files: string[];
}

export interface FormQuestionFieldDTO {
  id: string;
  type: string;
  techName: string;
  title: string;
  description: string;
  options: FormOptionDTO[];
  validation: string[];
  dictionaryName?: string | null;
  readOnly: boolean;
  repeatingSectionGrid: FormQuestionDTO[];
  defaultValue?: string | string[] | null;
  defaultValueType?: string | null;
  consentSectionConfig?: ConsentSectionConfigDTO | null;
  states: FieldStateDTO[];
  questionOrder: number;
  tooltipMessage: string;
  multiLevelTree?: boolean | null;
  searchEnabled?: boolean | null;
}

export interface FormQuestionDTO {
  x: number;
  y: number;
  rows: number;
  cols: number;
  field: FormQuestionFieldDTO;
}

export interface FormTabDTO {
  id: string;
  title: string;
  type: 'MAIN' | 'FINISH';
  questions: FormQuestionDTO[];
}

export interface FlowLinkDTO {
  id: string;
  source: string;
  target: string;
}

export interface FormFlowDTO {
  links: FlowLinkDTO[];
}

export interface FormDefinitionDTO {
  title: string;
  tabs: FormTabDTO[];
  flow: FormFlowDTO;
}

export interface DigitizeResponseDTO {
  status: string;
  filename: string;
  extension: string;
  size_bytes: number;
  detected_mime: string;
  extracted: ExtractedDocument | null;
  structured_form?: StructuredFormDTO | null;
  form_definition?: FormDefinitionDTO | null;
  structuring_mode: 'heuristic' | 'llm' | 'heuristic_fallback';
}

export interface HealthResponseDTO {
  status: string;
  ai_provider: string;
  service: string;
  version: string;
  llm_enabled: boolean;
  ai_model: string;
  llm_status: 'disabled' | 'configured' | 'ready' | 'unreachable';
}

export interface LlmWarmupResponseDTO {
  status: 'ready' | 'disabled' | 'unreachable';
  model: string;
  latency_ms: number;
  detail?: string | null;
}

export interface ApiErrorDetail {
  status: number;
  message: string;
  detail?: string;
}
