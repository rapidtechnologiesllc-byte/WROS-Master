import { renderAsync } from "docx-preview";
import { useEffect, useRef } from "react";

const DocxViewer = ({ blob }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    if (blob && containerRef.current) {
      renderAsync(blob, containerRef.current);
    }
  }, [blob]);

  return <div ref={containerRef} />;
};

export default DocxViewer;
