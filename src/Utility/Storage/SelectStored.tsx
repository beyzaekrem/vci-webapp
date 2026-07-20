
/**
 * A select component that stores the selected value in local storage or url, using the useStored hook.
 * @packageDocumentation
 */

import Select, { components } from "react-select";
import { StoredHookOptions, useStored } from "./useStored";


export function SelectStored<T>({ storageSettings, label, formattedOptions }: { storageSettings: StoredHookOptions<T>, label: string, formattedOptions: { value: T, label: string }[] }) {

    const [currentValue, setValue] = useStored(storageSettings);

    return <div style={{ display: 'inline-block', minWidth: '200px' }}>
        <Select<{ value: T, label: string }>
            options={formattedOptions}
            value={formattedOptions.find(option => option.value === currentValue)}
            onChange={selectedOption => {
                const newValue = selectedOption ? selectedOption.value : storageSettings.defaultValue;
                setValue(newValue)
            }}
            styles={{ container: base => ({ ...base, width: 'auto', zIndex: 100 }) }}
            components={{
                SingleValue: (props) => <components.SingleValue {...props}>
                    {label}{props.children}
                </components.SingleValue>
            }}
        />
    </div>
}
