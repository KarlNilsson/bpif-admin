import type { components } from './api.ts';

export type PaymentRequest = components['schemas']['PaymentRequestRead'];
export type PaymentRequestCreate = components['schemas']['PaymentRequestCreate'];
export type PaymentRequestAdmin = components['schemas']['PaymentRequestAdminRead'];
export type PaymentRequestList = components['schemas']['PaymentRequestList'];
export type LinkedFee = components['schemas']['LinkedFeeRead'];
export type MarkFeesPaidResult = components['schemas']['MarkFeesPaidResult'];
