/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  options: {
    // Only show dependencies where BOTH the importer and imported file are in src/Components or src/pages
    includeOnly: {
      path: '^src/Components|^src/pages'
    },
    exclude: {
      path: 'Icons.tsx'
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
        //collapsePattern: '^src/Components/Parameters',
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
            {
              criteria: { source: '^src/Components/CameraHooks(?:/|$)' },
              attributes: { fillcolor: '#f48fb1', color: '#ad1457' }
            },
            {
              criteria: { source: '^src/Components/Capture(?:/|$)' },
              attributes: { fillcolor: '#80cbc4', color: '#00695c' }
            },
            {
              criteria: { source: '^src/Components/Config(?:/|$)' },
              attributes: { fillcolor: '#64b5f6', color: '#0d47a1' }
            },
            {
              criteria: { source: '^src/Components/ControlServerInfo(?:/|$)' },
              attributes: { fillcolor: '#ef9a9a', color: '#b71c1c' }
            },
            {
              criteria: { source: '^src/Components/Parameters(?:/|$)' },
              attributes: { fillcolor: '#ffb74d', color: '#e65100' }
            },
            {
              criteria: { source: '^src/Components/SelectCameras(?:/|$)' },
              attributes: { fillcolor: '#fff176', color: '#f57f17' }
            },
            {
              criteria: { source: '^src/Components/Sidebar(?:/|$)' },
              attributes: { fillcolor: '#ba68c8', color: '#6a1b9a' }
            },
            {
              criteria: { source: '^src/Components/Videostream(?:/|$)' },
              attributes: { fillcolor: '#81c784', color: '#1b5e20' }
            },
            {
              criteria: { source: '^src/pages(?:/|$)' },
              attributes: { fillcolor: '#b39ddb', color: '#4527a0' }
            }
          ],
          dependencies: [
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
            {
              criteria: { resolved: '^src/Components/CameraHooks(?:/|$)' },
              attributes: { color: '#ad145788' }
            },
            {
              criteria: { resolved: '^src/Components/Capture(?:/|$)' },
              attributes: { color: '#00695c88' }
            },
            {
              criteria: { resolved: '^src/Components/Config(?:/|$)' },
              attributes: { color: '#0d47a188' }
            },
            {
              criteria: { resolved: '^src/Components/ControlServerInfo(?:/|$)' },
              attributes: { color: '#b71c1c88' }
            },
            {
              criteria: { resolved: '^src/Components/Parameters(?:/|$)' },
              attributes: { color: '#e6510088' }
            },
            {
              criteria: { resolved: '^src/Components/SelectCameras(?:/|$)' },
              attributes: { color: '#f57f1788' }
            },
            {
              criteria: { resolved: '^src/Components/Sidebar(?:/|$)' },
              attributes: { color: '#6a1b9a88' }
            },
            {
              criteria: { resolved: '^src/Components/Videostream(?:/|$)' },
              attributes: { color: '#1b5e2088' }
            },
            {
              criteria: { resolved: '^src/pages(?:/|$)' },
              attributes: { color: '#4527a088' }
            },
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
  forbidden: []
};
