import type { FieldStateDTO, FormDefinitionDTO } from '../types/digitize';

export type CoiUserAnswer = string | string[];
export type CoiUserAnswers = Record<string, CoiUserAnswer>;

const STATE_QUERY_PATTERN = /^\s*(\$not\s*\()?\s*("(?:\\.|[^"\\])*")\s+in\s+([\s\S]*?\.field\.__userAnswer)\s*\)?\s*$/;
const TECH_NAME_PATTERN = /questions\['((?:\\.|[^'\\])*)' in field\.techName\]/g;

export function evaluateCoiState(
  state: FieldStateDTO,
  answers: CoiUserAnswers,
): boolean {
  if (state.type !== 'SHOW') return true;

  const match = STATE_QUERY_PATTERN.exec(state.query);
  if (!match) return true;

  let option: string;
  try {
    option = JSON.parse(match[2]) as string;
  } catch {
    return true;
  }

  const selectors = [...match[3].matchAll(TECH_NAME_PATTERN)];
  const encodedTechName = selectors.at(-1)?.[1];
  if (!encodedTechName) return true;

  const techName = encodedTechName.replace(/\\'/g, "'").replace(/\\\\/g, '\\');
  const answer = answers[techName];
  const containsOption = Array.isArray(answer) ? answer.includes(option) : answer === option;
  return match[1] ? !containsOption : containsOption;
}

export function areCoiStatesVisible(
  states: FieldStateDTO[],
  answers: CoiUserAnswers,
): boolean {
  return states.every((state) => evaluateCoiState(state, answers));
}

export function getCoiExportFilename(title: string): string {
  const polishLetters: Record<string, string> = {
    ą: 'a', ć: 'c', ę: 'e', ł: 'l', ń: 'n', ó: 'o', ś: 's', ź: 'z', ż: 'z',
  };
  const slug = title
    .trim()
    .toLocaleLowerCase('pl-PL')
    .replace(/[ąćęłńóśźż]/g, (letter) => polishLetters[letter] ?? letter)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  return `konfiguracja_form_${slug || 'formularz'}.json`;
}

export function serializeCoiFormDefinition(definition: FormDefinitionDTO): string {
  return `${JSON.stringify(definition, null, 2)}\n`;
}

export function downloadCoiFormDefinition(definition: FormDefinitionDTO): void {
  const blob = new Blob([serializeCoiFormDefinition(definition)], {
    type: 'application/json;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = getCoiExportFilename(definition.title);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
