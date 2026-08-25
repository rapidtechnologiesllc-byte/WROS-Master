/**
 * ESLint Rule: no-silent-catch-returns
 *
 * Prevents silent failures in catch blocks by detecting patterns where
 * exceptions are caught and empty values are returned without re-raising.
 *
 * CRITICAL: catch blocks must ALWAYS either:
 * 1. Re-throw the error: throw new Error(...)
 * 2. Log + throw: logger.error(...); throw new Error(...)
 * 3. Return with explicit logged warning + status code
 *
 * NEVER silently return [], {}, null, or undefined without logging
 *
 * Installation:
 * 1. Copy this file to project root as .eslintrc.no-silent-catch.js
 * 2. Add to .eslintrc: "extends": ["./.eslintrc.no-silent-catch.js"]
 */

module.exports = {
  rules: {
    'no-silent-catch-returns': {
      meta: {
        type: 'problem',
        docs: {
          description:
            'Prevent silent failures in catch blocks by detecting empty returns without error propagation',
          category: 'Best Practices',
          recommended: true,
        },
        messages: {
          silentReturn: 'Silent return of {{ value }} in catch block. Always re-throw or log + throw.',
          silentEmpty: 'Silent return of empty {{ type }} in catch block. Must re-throw exception.',
          silentNull: 'Silently returning {{ value }} in catch block. Must re-throw exception.',
        },
      },

      create(context) {
        return {
          CatchClause(node) {
            const body = node.body;

            // Check each statement in catch block
            body.body.forEach((statement) => {
              // Pattern 1: return []
              if (
                statement.type === 'ReturnStatement' &&
                statement.argument &&
                statement.argument.type === 'ArrayExpression' &&
                statement.argument.elements.length === 0
              ) {
                context.report({
                  node: statement,
                  messageId: 'silentEmpty',
                  data: { type: 'array' },
                });
              }

              // Pattern 2: return {}
              if (
                statement.type === 'ReturnStatement' &&
                statement.argument &&
                statement.argument.type === 'ObjectExpression' &&
                statement.argument.properties.length === 0
              ) {
                context.report({
                  node: statement,
                  messageId: 'silentEmpty',
                  data: { type: 'object' },
                });
              }

              // Pattern 3: return null/undefined
              if (
                statement.type === 'ReturnStatement' &&
                statement.argument &&
                (statement.argument.type === 'Literal' && statement.argument.value === null ||
                 statement.argument.type === 'Identifier' && statement.argument.name === 'undefined')
              ) {
                context.report({
                  node: statement,
                  messageId: 'silentNull',
                  data: { value: 'null/undefined' },
                });
              }

              // Pattern 4: return value without prior throw/throw-like call
              if (
                statement.type === 'ReturnStatement' &&
                statement.argument
              ) {
                // Check if there's a preceding throw statement
                const hasThrow = body.body.some(
                  (s, idx) => s.type === 'ThrowStatement' && idx < body.body.indexOf(statement)
                );

                // Check if there's a preceding console.error or logger call
                const hasLogging = body.body.some(
                  (s, idx) => {
                    if (idx >= body.body.indexOf(statement)) return false;
                    if (s.type === 'ExpressionStatement') {
                      const expr = s.expression;
                      // Match: console.error(...), logger.error(...), toast.error(...)
                      if (
                        expr.type === 'CallExpression' &&
                        expr.callee.type === 'MemberExpression' &&
                        ['error', 'warn', 'critical'].includes(expr.callee.property.name)
                      ) {
                        return true;
                      }
                    }
                    return false;
                  }
                );

                // If returning without throw or logging, it's suspicious
                // But allow it if it's returning a status/error object with explicit structure
                const isStatusObject =
                  statement.argument.type === 'ObjectExpression' &&
                  statement.argument.properties.some(
                    (p) =>
                      p.key.name === 'status' ||
                      p.key.name === 'error' ||
                      p.key.name === 'message'
                  );

                if (!hasThrow && !hasLogging && !isStatusObject) {
                  // This is a silent return - only flag simple values
                  if (
                    statement.argument.type === 'Identifier' ||
                    statement.argument.type === 'Literal'
                  ) {
                    context.report({
                      node: statement,
                      messageId: 'silentReturn',
                      data: {
                        value:
                          statement.argument.type === 'Identifier'
                            ? statement.argument.name
                            : JSON.stringify(statement.argument.value),
                      },
                    });
                  }
                }
              }
            });
          },
        };
      },
    },
  },
};
