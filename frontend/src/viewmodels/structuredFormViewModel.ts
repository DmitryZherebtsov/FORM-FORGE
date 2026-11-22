import type { StructuredFormDTO } from '../types/digitize';

export function updateStructuredField(
  form: StructuredFormDTO,
  sectionId: string,
  fieldId: string,
  value: string
): StructuredFormDTO {
  const sections = form.sections.map((section) =>
    section.section_id !== sectionId
      ? section
      : {
          ...section,
          fields: section.fields.map((field) =>
            field.field_id !== fieldId
              ? field
              : {
                  ...field,
                  value,
                  needs_review: !field.is_valid || !value.trim() || field.confidence < 0.8,
                }
          ),
        }
  );
  return updateFieldSummary(form, sections);
}

export function updateStructuredChoice(
  form: StructuredFormDTO,
  sectionId: string,
  groupId: string,
  optionIndex: number,
  isSelected: boolean
): StructuredFormDTO {
  const sections = form.sections.map((section) =>
    section.section_id !== sectionId
      ? section
      : {
          ...section,
          choice_groups: section.choice_groups.map((group) => {
            if (group.group_id !== groupId) return group;
            const options = group.options.map((option, index) => ({
              ...option,
              is_selected:
                group.selection_type === 'single'
                  ? index === optionIndex && isSelected
                  : index === optionIndex
                    ? isSelected
                    : option.is_selected,
            }));
            const selectedCount = options.filter((option) => option.is_selected).length;
            return {
              ...group,
              options,
              needs_review:
                group.selection_type === 'single' ? selectedCount !== 1 : group.needs_review,
            };
          }),
        }
  );
  return updateFieldSummary(form, sections);
}

function updateFieldSummary(
  form: StructuredFormDTO,
  sections: StructuredFormDTO['sections']
): StructuredFormDTO {
  const fields = sections.flatMap((section) => section.fields);
  return {
    ...form,
    sections,
    total_fields: fields.length,
    fields_needing_review: fields.filter((field) => field.needs_review).length,
  };
}
