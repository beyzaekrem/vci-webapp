
export const ImageDisplayWidget = ({ value, label }: { value: string | null | undefined; label: string }) => {

    const imageUri = `data:image/png;base64,${value}`;
    return <div>
        {value ? (
            <img
                src={imageUri}
                alt={label}
                style={{ maxWidth: "100%" }}
            />
        ) : (
            <div>No image</div>
        )}
    </div>
}


type ImageDisplayObjectValue = {
    caption?: string;
    image_uri?: string;
} | null | undefined;

export const ObjectImageDisplayWidget = ({
    value,
    label,
}: {
    value: ImageDisplayObjectValue;
    label: string;
}) => {
    const imageUri = value?.image_uri;
    const caption = value?.caption ?? label;

    return (
        <div>
            {imageUri ? (
                <>
                    <img
                        src={imageUri}
                        alt={caption}
                        style={{ maxWidth: "100%", maxHeight: 240 }}
                    />
                    {value?.caption && <div className="mt-2">{value.caption}</div>}
                </>
            ) : (
                <div>No image</div>
            )}
        </div>
    );
};