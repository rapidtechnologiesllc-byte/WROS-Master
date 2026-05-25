import styled from "styled-components";
import { Select } from "antd";

export const SelectWrapper = styled.div`
  width: 100%;
  margin-bottom: 16px;
`;

export const Label = styled.label`
  display: block;
  margin-bottom: 8px;

  font-size: 14px;
  font-weight: 500;
  color: #333;
`;

export const StyledSelect = styled(Select)`
  width: 100%;

  &.ant-select-outlined {
    border-color: #d1d5db !important;
    box-shadow: none !important;
  }

  :hover &.ant-select-outlined {
    border-color: #9ca3af !important;
    box-shadow: none !important;
  }

  .anticon-search {
    display: none !important;
  }

  .anticon-down {
    display: none !important;
  }

  .ant-select-selector {
    height: 46px !important;
    border-radius: 14px !important;
    border: 1px solid #d9d9d9 !important;
    background: #fff !important;

    display: flex;
    align-items: center;

    padding: 0 14px !important;
    box-shadow: none !important;
  }

  .ant-select-selection-placeholder {
    color: #bfbfbf !important;
    font-size: 16px;
  }

  .ant-select-selection-item {
    font-size: 16px;
    color: #333;
    line-height: 44px !important;
  }

  .ant-select-arrow {
    color: #999;
    font-size: 12px;
  }

  &:hover .ant-select-selector {
    border-color: #cfcfcf !important;
  }

  &.ant-select-focused .ant-select-selector {
    border-color: #cfcfcf !important;
    box-shadow: none !important;
  }
`;
