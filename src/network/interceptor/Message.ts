/**
 * Message types and helpers for encoding and decoding interceptor traffic.
 * @packageDocumentation
 */
import { BSON } from "bson";

/**
 * Base interface for messages exchanged between clients and servers.
 * Contains common properties such as ID, TYPE, PATH, ERROR, and META.
 * Does not contain the PAYLOAD field, because that one means different things before and after decoding/encoding (see MessageOutRaw vs MessageOut).
 */
/**
 * Common fields shared by all interceptor messages.
 */
interface MessageBase {
    ID: number;
    TYPE: MessageType;
    PATH?: string;
    ERROR?: string;
    META?: any;
}


/**
 * Enum representing the different types of messages used in the network interceptor.
 *
 * @remarks
 * This enum is used to categorize messages exchanged between clients and servers,
 * specifying their intent and expected handling behavior.
 *
 * @enum {number}
 * @property {number} MessageTypeNotSet - Indicates that the message type has not been properly set.
 * @property {number} ProtocolMessage - Represents messages not intended for clients, typically protocol-level.
 * @property {number} ErrorMessage - Represents error messages that are not the result of a specific message.
 * @property {number} StandardMessage - A normal message that expects a response.
 * @property {number} MonologueMessage - A normal message that does not expect a response.
 * @property {number} AcknowledgeResponse - An acknowledgment response to a StandardMessage.
 * @property {number} ErrorResponse - An error response to a StandardMessage.
 */
export enum MessageType {
    MessageTypeNotSet = 0,
    ProtocolMessage = 1,
    ErrorMessage = 2,
    StandardMessage = 3,
    MonologueMessage = 4,
    AcknowledgeResponse = 5,
    ErrorResponse = 6
}

/**
 * Contains Info about a Payload that is appended to the BSON header.
 */
/**
 * Header entry describing a single appended payload.
 */
interface PayloadInfo {
    SIZE: number;
    TYPE: number;
    META?: any;
}

/**
 * Payload encoding types defined by interceptor.
 */
enum PayloadType {
    RawPtrPayload = 0,// Raw buffer
    StringPayload = 1,// String
    BsonPayload = 2
}

/**
 * Decoded payloads can be of any type.
 * This type only renames the "any" type to "Payload" for better readability.
 */
type Payload = any
/**
 * Class for sending/receiving messages over a WebSocket connection.
 * When a message like this is sent, the message is serialized to BSON.
 * When a message is is received, the binary data is decoded from BSON to this format and contains the appended payloads.
 *
 * @template PAYLOAD - An array containing the payload data to be sent/ received.
 */
export interface Message extends MessageBase {
    PAYLOAD: Array<Payload>;
}


//----------------------- Helper Interfaces for decoding/encoding -----------------------//

/**
 * Type of the received messages, as defined in interceptor.
 * Not that the PAYLOAD field only contains the size and type of the payloads and not the payloads themselves.
 * They are appended after this object in the Buffer.
 */
/**
 * Raw message header received from the server before payloads are appended.
 */
interface MessageInRaw extends MessageBase {
    PAYLOAD?: Array<PayloadInfo>;

}

/**
 * Type of Messages to send, as defined in interceptor.
 * Note that the PAYLOAD field only contains the size and type of the payloads and not the payloads themselves.
 * They are appended after this object in the Buffer.
 */
/**
 * Raw message header to send before payloads are appended.
 */
interface MessageOutRaw extends MessageBase {
    PAYLOAD: {
        SIZE: number;
        TYPE: PayloadType;
    }[];
}


//----------------------- Decoding/Encoding Functions -----------------------//

/**
 * Decodes a binary WebSocket message into a structured `Message` object.
 *
 * The message format is expected to be as specified for interceptor:
 * - The first 4 bytes (little-endian) specify the size of the BSON header.
 * - The next `header_size` bytes contain the BSON-encoded header.
 * - Additional payloads may be appended, as described in the header's `PAYLOAD` field.
 *   Each payload entry specifies its size and type, which can be BSON, string, or raw bytes.
 *
 * @param data - The binary data received from the WebSocket.
 * @returns The decoded message as a `Message` object.
 */

export function decodeWebsocketMessage(
    data: ArrayBufferLike
): Message {
    //console.log("Received data: ", data);
    var dataView = new DataView(data);

    // Decode the first 4 bytes as a number
    const header_size = dataView.getUint32(0, true);
    //console.log("First 4 bytes as number: ", header_size);
    // Decode the first header_size bytes as BSON (with first 4 bytes)
    const bsonData = new Uint8Array(data, 0, header_size);
    const bsonMessage = BSON.deserialize(bsonData);

    // Decode the payload objects that are appended to the BSON message
    const appended_payload = [] as Array<any>;
    let offset = header_size;
    const payloadInfo = (bsonMessage as MessageInRaw).PAYLOAD;
    if(payloadInfo) {
        let i = 0;
        for(const payload of payloadInfo) {
            const size = payload.SIZE;
            var type = payload.TYPE;

            switch(type) {
                case PayloadType.BsonPayload:
                    const bsonPayload = new Uint8Array(data, offset, size);
                    const decodedPayload = BSON.deserialize(bsonPayload);
                    appended_payload.push(decodedPayload);
                    break;
                case PayloadType.StringPayload:
                    const stringPayload = new TextDecoder().decode(
                        new Uint8Array(data, offset, size)
                    );
                    appended_payload.push(stringPayload);
                    break;
                case PayloadType.RawPtrPayload:
                    const rawPtrPayload = new Uint8Array(data, offset, size);
                    appended_payload.push(rawPtrPayload);
                    break;
                default:
                    console.error("Unknown payload type: " + type);
            }
            offset += size;
            i++;
        }
    }

    const decodedMessage = {
        ...bsonMessage,
        PAYLOAD: appended_payload,
    } as Message;

    //console.log("Decoded Bson message: ", decodedMessage);
    return decodedMessage;
}

/**
 * Encodes a `MessageOutWrapper` object into the binary format specified for interceptor.
 *
 * @param msg - The `MessageOutWrapper` object to encode.
 * @returns An `ArrayBuffer` containing the encoded message.
 */
export function encodeWebsocketMessage(
    msg: Message
): ArrayBuffer {

    const payloadObjects = msg.PAYLOAD.map((payloadObject) => {
        const bsonPayload = BSON.serialize(payloadObject);
        return {
            SIZE: bsonPayload.byteLength,
            TYPE: PayloadType.BsonPayload,
            bsonPayload,
        };
    });

    const message: MessageOutRaw = {
        TYPE: msg.TYPE,
        ID: msg.ID,
        PATH: msg.PATH,
        PAYLOAD: payloadObjects.map((obj) => ({
            SIZE: obj.SIZE,
            TYPE: obj.TYPE,
        })),
    };

    const bsonMessage = BSON.serialize(message);
    const totalSize =
        bsonMessage.byteLength +
        payloadObjects.reduce((acc, obj) => acc + obj.SIZE, 0);
    const combinedMessage = new Uint8Array(totalSize);

    combinedMessage.set(new Uint8Array(bsonMessage), 0);
    let offset = bsonMessage.byteLength;
    payloadObjects.forEach((obj) => {
        combinedMessage.set(new Uint8Array(obj.bsonPayload), offset);
        offset += obj.SIZE;
    });

    return combinedMessage.buffer;
}
