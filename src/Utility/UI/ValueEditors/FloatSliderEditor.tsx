import React, { useState, useEffect } from 'react';
import { Form } from 'react-bootstrap';
import './editors.css';
import { NumberEditorProps } from './types';


export const FloatSliderEditor: React.FC<NumberEditorProps> = ({
    value,
    min,
    max,
    increment,
    onChange,
}) => {
    const [valueStr, setValueStr] = useState(value.toString());
    const [minStr, setMinStr] = useState(min !== undefined ? min.toString() : '');
    const [maxStr, setMaxStr] = useState(max !== undefined ? max.toString() : '');
    const [incStr, setIncStr] = useState(increment !== undefined ? increment.toString() : '');
    const [editingIncrement, setEditingIncrement] = useState(false);

    useEffect(() => { setValueStr(value.toString()); }, [value]);
    useEffect(() => { setMinStr(min !== undefined ? min.toString() : ''); }, [min]);
    useEffect(() => { setMaxStr(max !== undefined ? max.toString() : ''); }, [max]);
    useEffect(() => { setIncStr(increment !== undefined ? increment.toString() : ''); }, [increment]);

    // Commit only the main value to the parent.
    const commitValue = () => {
        const newValue = valueStr === '' ? NaN : parseFloat(valueStr);
        if(!isNaN(newValue)) {
            onChange(newValue);
        }
    };

    // Use local state to determine the slider’s boundaries and step.
    const sliderMin = minStr !== '' ? parseFloat(minStr) : 0;
    const sliderMax = maxStr !== '' ? parseFloat(maxStr) : 100;
    const sliderStep = incStr !== '' ? parseFloat(incStr) : 1;

    return (
        <div className="w-100">
            <div className="d-flex align-items-center mb-2">
                <Form.Control
                    type="number"
                    placeholder="Min"
                    value={minStr}
                    onChange={(e) => setMinStr(e.target.value)}
                    className='range-input'
                />
                <Form.Range
                    className="flex-grow-1 mx-2"
                    value={valueStr}
                    min={sliderMin}
                    max={sliderMax}
                    step={sliderStep}
                    onChange={(e) => {
                        const newVal = parseFloat(e.target.value);
                        setValueStr(e.target.value);
                        onChange(newVal);
                    }}
                />
                <Form.Control
                    type="number"
                    placeholder="Max"
                    value={maxStr}
                    onChange={(e) => setMaxStr(e.target.value)}
                    className='range-input'
                />
            </div>
            <div className="mb-2">
                <Form.Control
                    type="number"
                    placeholder="Value"
                    value={valueStr}
                    onChange={(e) => setValueStr(e.target.value)}
                    onBlur={commitValue}
                    className="text-center"
                />
            </div>
            <div className="d-flex align-items-center">
                <span style={{ marginRight: '10px' }}>Increment:</span>
                {editingIncrement ? (
                    <Form.Control
                        type="number"
                        placeholder="Step"
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
