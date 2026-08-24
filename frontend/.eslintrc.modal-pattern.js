/**
 * ESLint Rule: Detect Modal Anti-Pattern
 *
 * Detects the scattered modal anti-pattern:
 * - showCreateModal + showEditModal state variables
 * - Separate create/edit modals in same component
 *
 * Requires refactoring to unified form pages pattern.
 */

module.exports = {
  rules: {
    'no-scattered-modals': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Detects scattered create/edit modal pattern - use unified form pages instead',
          category: 'Best Practices',
          recommended: true,
        },
        messages: {
          scatteredModals: 'Scattered modals detected: {{pattern}}. Use dedicated form pages instead (see PATTERN.md)',
          createEditState: 'showCreateModal + showEditModal pattern detected - refactor to form page',
        },
      },
      create(context) {
        const sourceCode = context.getSourceCode();
        let stateVars = [];

        return {
          VariableDeclarator(node) {
            if (node.id.name && node.id.name.includes('show')) {
              if (node.id.name.includes('CreateModal') || node.id.name.includes('EditModal')) {
                stateVars.push(node.id.name);
              }
            }
          },
          'Program:exit'(node) {
            if (stateVars.length >= 2) {
              const hasCreate = stateVars.some(v => v.includes('CreateModal'));
              const hasEdit = stateVars.some(v => v.includes('EditModal'));

              if (hasCreate && hasEdit) {
                context.report({
                  node,
                  messageId: 'createEditState',
                  data: { pattern: stateVars.join(', ') },
                });
              }
            }
          },
        };
      },
    },
  },
};
