/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  options: {
    // Only show dependencies where BOTH the importer and the imported file are in src/
    includeOnly: {
      path: '^src'
    },

    // Extra belt-and-suspenders: don't follow anything in node_modules
    doNotFollow: {
      path: 'node_modules'
    },

    // Resolve TS/TSX nicely
    tsConfig: {
      fileName: 'tsconfig.json'
    },
    enhancedResolveOptions: {
      extensions: ['.ts', '.tsx', '.js', '.jsx']
    },
    // Include type-only dependencies (interfaces/types) from TS/TSX
    tsPreCompilationDeps: true,
    reporterOptions: {
      dot: {
        // Collapse everything under src/Components into a single node for now
        collapsePattern: '^src/Components',
        theme: {
          graph: {
            bgcolor: '#fbfcff'
          },
          node: {
            style: 'rounded,filled',
            color: '#3d4a5c'
          },
          edge: {
            color: '#4a556833'
          },
          modules: [
            // Keep violations prominent over category colors
            {
              criteria: { 'rules[0].severity': 'error' },
              attributes: { fontcolor: '#b00020', color: '#b00020', penwidth: 2.2 }
            },
            {
              criteria: { 'rules[0].severity': 'warn' },
              attributes: { fontcolor: '#e65100', color: '#e65100', penwidth: 2.0 }
            },
            {
              criteria: { 'rules[0].severity': 'info' },
              attributes: { fontcolor: '#0d47a1', color: '#0d47a1' }
            },

            // App shell
            // Feature and domain areas
            {
              criteria: { source: '^src/Components(?:/|$)' },
              attributes: { fillcolor: '#63cdda', color: '#1b7f8d' }
            },
            {
              criteria: { source: '^src/pages(?:/|$)' },
              attributes: { fillcolor: '#6585cf', color: '#0645d9' }
            },
            {
              criteria: { source: '^src/Utility/Storage(?:/|$)' },
              attributes: { fillcolor: '#c8e6c9', color: '#2e7d32' }
            },
            {
              criteria: { source: '^src/Utility/KeyBindings(?:/|$)' },
              attributes: { fillcolor: '#dd9be2', color: '#df64e8' }
            },
            {
              criteria: { source: '^src/Utility/UI(?:/|$)' },
              attributes: { fillcolor: '#d7ccc8', color: '#6d4c41' }
            },
            {
              criteria: { source: '^src/Utility/Notifications(?:/|$)' },
              attributes: { fillcolor: '#ffecb3', color: '#ff8f00' }
            },
            {
              criteria: { source: '^src/network/capture-server(?:/|$)' },
              attributes: { fillcolor: '#ffccbc', color: '#d84315' }
            },
            {
              criteria: { source: '^src/network/control-server(?:/|$)' },
              attributes: { fillcolor: '#c5cae9', color: '#3949ab' }
            },
            {
              criteria: { source: '^src/network/interceptor(?:/|$)' },
              attributes: { fillcolor: '#ffe0b2', color: '#ef6c00' }
            },
            {
              criteria: { source: '^src/network/vci-automation(?:/|$)' },
              attributes: { fillcolor: '#1e790783', color: '#1e7907' }
            }
          ],
          dependencies: [
            // Keep violations prominent over category colors
            {
              criteria: { 'rules[0].severity': 'error' },
              attributes: { color: '#b00020', fontcolor: '#b00020', penwidth: 2.4 }
            },
            {
              criteria: { 'rules[0].severity': 'warn' },
              attributes: { color: '#e65100', fontcolor: '#e65100', penwidth: 2.1 }
            },
            {
              criteria: { 'rules[0].severity': 'info' },
              attributes: { color: '#0d47a1', fontcolor: '#0d47a1', penwidth: 2.0 }
            },

            // Domain-colored edges by target module
            {
              criteria: { resolved: '^src/Components(?:/|$)' },
              attributes: { color: '#1b7f8d88' }
            },
            {
              criteria: { resolved: '^src/pages(?:/|$)' },
              attributes: { color: '#0645d988' }
            },
            {
              criteria: { resolved: '^src/Utility/Storage(?:/|$)' },
              attributes: { color: '#2e7d3288' }
            },
            {
              criteria: { resolved: '^src/Utility/KeyBindings(?:/|$)' },
              attributes: { color: '#df64e888' }
            },
            {
              criteria: { resolved: '^src/Utility/UI(?:/|$)' },
              attributes: { color: '#6d4c4188' }
            },
            {
              criteria: { resolved: '^src/Utility/Notifications(?:/|$)' },
              attributes: { color: '#ff8f0088' }
            },
            {
              criteria: { resolved: '^src/network/capture-server(?:/|$)' },
              attributes: { color: '#d8431588' }
            },
            {
              criteria: { resolved: '^src/network/control-server(?:/|$)' },
              attributes: { color: '#3949ab88' }
            },
            {
              criteria: { resolved: '^src/network/interceptor(?:/|$)' },
              attributes: { color: '#ef6c0088' }
            },
            {
              criteria: { resolved: '^src/network/vci-automation(?:/|$)' },
              attributes: { color: '#1e7907' }
            },

            // Keep special relation types recognizable
            {
              criteria: {
                dependencyTypes: [
                  'pre-compilation-only',
                  'triple-slash-type-reference',
                  'type-import',
                  'type-only'
                ]
              },
              attributes: { arrowhead: 'onormal', penwidth: '1.2', style: 'dashed' }
            },
            {
              criteria: { dependencyTypes: ['export'] },
              attributes: { arrowhead: 'inv', penwidth: '1.4' }
            }
          ]
        }
      }
    }
  },
  forbidden: [
    {
      name: 'utility-no-outside-deps',
      comment: 'Utility must not depend on code outside its own module',
      severity: 'error',

      from: {
        path: '^src/Utility'
      },

      to: {
        // anything NOT inside src/Utility
        pathNot: '^src/Utility'
      }
    },
    {
      name: 'utility-only-barrel-imports',
      comment: 'Utility modules should only be imported via the barrel files in the respective subdirectories',
      severity: 'error',
      from: {
        pathNot: '^src/Utility'
      },
      to: {
        path: '^src/Utility',
        pathNot: '^src/Utility/(index\\.ts|[^/]+/index\\.ts)$'
      }
    },
    {
      name: 'pages-only-imported-by-router',
      comment: 'Page modules should only be imported by the top-level router',
      severity: 'error',
      from: {
        pathNot: '^src/router\\.tsx$'
      },
      to: {
        path: '^src/pages/index\\.ts$'
      }
    },
    {
      name: 'network-no-ui-deps',
      comment: 'Network layer must not depend on UI (Components or pages)',
      severity: 'error',
      from: {
        path: '^src/network'
      },
      to: {
        path: '^src/(Components|pages)'
      }
    },
    {
      name: 'network-no-outside-deps', //TODO think about wether this is a good idea or not
      comment: 'Network layer must not depend on code outside its own module, except for src/Utility/Storage',
      severity: 'error',
      from: {
        path: '^src/network'
      },
      to: {
        pathNot: ['^src/network', '^src/Utility/Storage']
      }
    },
    {
      name: "network-only-barrel-imports",
      comment: "Network modules should only be imported via the barrel files in the respective subdirectories",
      severity: "error",
      from: {
        pathNot: "^src/network"
      },
      to: {
        path: "^src/network",
        pathNot:
          "^src/network/(index\\.ts|capture-server(?:/index\\.ts)?|control-server(?:/index\\.ts)?|interceptor(?:/index\\.ts)?|vci-automation(?:/index\\.ts)?)$"
      }
    },
    {
      name: `capture-server-only-barrel-imports`,
      severity: 'error',
      from: {
        pathNot: '^src/network/capture-server'
      },
      to: {
        path: '^src/network/capture-server',
        pathNot: '^src/network/capture-server/index\\.ts$'
      }
    },
    {
      name: `control-server-only-barrel-imports`,
      severity: 'error',
      from: {
        pathNot: '^src/network/control-server'
      },
      to: {
        path: '^src/network/control-server',
        pathNot: '^src/network/control-server/index\\.ts$'
      }
    },
    {
      name: "vci-automation-only-barrel-imports",
      severity: "error",
      from: {
        pathNot: "^src/Components/vci-automation"
      },
      to: {
        path: "^src/Components/vci-automation",
        pathNot: "^src/Components/vci-automation/index\\.ts$"
      }
    },
    {
      name: `interceptor-only-barrel-imports`,
      severity: 'error',
      from: {
        pathNot: '^src/network/interceptor'
      },
      to: {
        path: '^src/network/interceptor',
        pathNot: '^src/network/interceptor/index\\.ts$'
      }
    },
    {
      name: 'capture-server-no-control-server',
      comment: 'Capture server module must not depend on control server module',
      severity: 'error',
      from: {
        path: '^src/network/capture-server'
      },
      to: {
        path: '^src/network/control-server'
      }
    },
    {
      name: 'control-server-no-capture-server',
      comment: 'Control server module must not depend on capture server module',
      severity: 'error',
      from: {
        path: '^src/network/control-server'
      },
      to: {
        path: '^src/network/capture-server'
      }
    },
    {
      name: 'interceptor-base-no-app-servers',
      comment: 'Interceptor base must not depend on capture/control server modules',
      severity: 'error',
      from: {
        path: '^src/network/interceptor'
      },
      to: {
        path: '^src/network/(capture-server|control-server)'
      }
    },
    {
      name: 'no-circular',
      comment: 'Disallow circular dependencies',
      severity: 'error',
      from: {},
      to: {
        circular: true
      }
    },
  ],
};
