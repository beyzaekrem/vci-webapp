
/**
 * Properties for a number editor component, used for both integer and float editors.
 */
export interface NumberEditorProps {
    value: number;
    min?: number;
    max?: number;
    increment?: number;
    onChange: (value: number) => void;
}
