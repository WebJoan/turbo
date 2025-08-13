"use client";

import { makeMarkdownText } from "@assistant-ui/react-markdown";

const BaseMarkdownText = makeMarkdownText();

type AnyProps = Record<string, unknown>;

export function MarkdownText(props: AnyProps) {
    const { componentsByLanguage, ...rest } = props;
    return <BaseMarkdownText {...rest} />;
}


