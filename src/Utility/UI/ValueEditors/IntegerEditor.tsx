import React, { useState, useEffect } from 'react';
import { Form } from 'react-bootstrap';
import './editors.css';
import { NumberEditorProps } from './types';

export const IntegerEditor: React.FC<NumberEditorProps> = ({
    value,
    min,
    max,
    increment,
    onChange,
}) => {
    // Local state is maintained for the main value and for min, max, and increment.
    const [valueStr, setValueStr] = useState(value.toString());
    const [minStr, setMinStr] = useState(min !== undefined ? min.toString() : '');
    const [maxStr, setMaxStr] = useState(max !== undefined ? max.toString() : '');
    const [incStr, setIncStr] = useState(increment !== undefined ? increment.toString() : '');
    const [editingIncrement, setEditingIncrement] = useState(false);

    useEffect(() => { setValueStr(value.toString()); }, [value]);
    // Optionally update these if the parent ever changes them.
    useEffect(() => { setMinStr(min !== undefined ? min.toString() : ''); }, [min]);
    useEffect(() => { setMaxStr(max !== undefined ? max.toString() : ''); }, [max]);
    useEffect(() => { setIncStr(increment !== undefined ? increment.toString() : ''); }, [increment]);

    // Only commit the main value to the parent.
    const commitValue = () => {
        const newValue = valueStr === '' ? NaN : parseInt(valueStr, 10);
        if(!isNaN(newValue)) {
            onChange(newValue);
        }
    };

    return (
        <div className="w-100">
            <div className="d-flex align-items-center mb-2">
                {/* min input: changes only local state */}
                <Form.Control
                    className='range-input'
                    type="number"
                    placeholder="Min"
                    value={minStr}
                    onChange={(e) => setMinStr(e.target.value)}
                    style={{ marginRight: '5px' }}
                />
                {/* main value input */}
                <Form.Control
                    type="number"
                    placeholder="Value"
                    value={valueStr}
                    onChange={(e) => setValueStr(e.target.value)}
                    onBlur={commitValue}
                    className="flex-grow-1 text-center"
                    style={{ marginRight: '5px' }}
                />
                {/* max input: changes only local state */}
                <Form.Control
                    type="number"
                    placeholder="Max"
                    value={maxStr}
                    onChange={(e) => setMaxStr(e.target.value)}
                    className='range-input'
                />
            </div>
            <div className="d-flex align-items-center">
                <span style={{ marginRight: '10px' }}>Increment:</span>
                {editingIncrement ? (
                    <Form.Control
                        type="number"
                        placeholder="Increment"
                        value={incStr}
                        onChange={(e) => setIncStr(e.target.value)}
                        onBlur={() => setEditingIncrement(false)}
                        style={{ width: '100px' }}
                    />
                ) : (
                    <div
                        style={{
                            width: '100px',
                            cursor: 'pointer',
                            border: '1px solid #ced4da',
                            padding: '0.375rem 0.75rem',
                            borderRadius: '0.25rem',
                        }}
                        onClick={() => setEditingIncrement(true)}
                    >
                        {incStr !== '' ? incStr : 'Undefined'}
                    </div>
                )}
            </div>
        </div>
    );
};